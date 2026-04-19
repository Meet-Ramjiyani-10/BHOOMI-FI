"""
train_cv_model.py — Training pipeline for the BhoomiFi Crop Health CV model.

HOW TO RUN (from ml-service/ directory):
    python train_cv_model.py

Images must be placed in the training_images/ sub-folders BEFORE running:
    training_images/
    ├── healthy/          ← at least 5 images per class recommended
    ├── mild_stress/
    ├── diseased/
    └── severe_damage/

Supported formats: JPEG, PNG, WEBP (anything PIL can open).

After a successful run the following files are written to ml-service/:
    crop_health_model.pth   ← best checkpoint (by validation accuracy)
    training_report.json    ← full training summary
"""

import json
import logging
import os
import time
from datetime import datetime, timezone

import torch
import torch.nn as nn
import torchvision
import torchvision.models as models
import torchvision.datasets as datasets
from torch.utils.data import DataLoader, random_split

from image_processor import ImageProcessor

# ===================================================================
# CONFIGURATION  — edit these values before training
# ===================================================================
TRAINING_DATA_DIR  = 'training_images_balanced/'
MODEL_SAVE_PATH    = 'crop_health_model.pth'
EPOCHS             = 15
BATCH_SIZE         = 16
LEARNING_RATE      = 0.001
VALIDATION_SPLIT   = 0.2
NUM_CLASSES        = 4
FREEZE_BACKBONE    = True    # True → only classifier layers are trained
DEVICE             = 'cpu'   # change to 'cuda' if a GPU is available
# ===================================================================

CLASS_NAMES = ['healthy', 'mild_stress', 'diseased', 'severe_damage']

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# STEP 1 — Dataset verification
# -------------------------------------------------------------------

def verify_dataset(data_dir: str) -> dict:
    """
    Check that the training directory and all four class sub-folders exist,
    count images per class, and print a summary.

    Args:
        data_dir: Path to the root dataset directory.

    Returns:
        dict mapping class name → image count.

    Raises:
        FileNotFoundError: If data_dir is missing.
        RuntimeError:      If total image count is below 10.
    """
    if not os.path.isdir(data_dir):
        raise FileNotFoundError(
            f"Training data directory '{data_dir}' not found.\n"
            "Create it and add crop images before running this script."
        )

    counts = {}
    valid_exts = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff'}

    for cls in CLASS_NAMES:
        cls_dir = os.path.join(data_dir, cls)
        os.makedirs(cls_dir, exist_ok=True)   # create if absent

        images = [
            f for f in os.listdir(cls_dir)
            if os.path.splitext(f)[1].lower() in valid_exts
        ]
        counts[cls] = len(images)

    total = sum(counts.values())

    print("\nDataset Summary")
    print("─" * 40)
    print(f"Found {total} images across {NUM_CLASSES} classes:")
    for cls in CLASS_NAMES:
        flag = "  ⚠ WARNING: fewer than 5 images" if counts[cls] < 5 else ""
        print(f"  {cls:<20} {counts[cls]:>4} images{flag}")
    print("─" * 40)

    for cls in CLASS_NAMES:
        if counts[cls] < 5:
            print(
                f"WARNING: '{cls}' has only {counts[cls]} image(s). "
                "Add more images for better accuracy."
            )

    if total < 10:
        raise RuntimeError(
            "Insufficient training data. "
            "Add images to training_images/ folders before training.\n"
            f"(Found {total} total; minimum required: 10)"
        )

    return counts


# -------------------------------------------------------------------
# STEP 2 — Data loading
# -------------------------------------------------------------------

def build_dataloaders(data_dir: str, batch_size: int):
    """
    Build train and validation DataLoaders using torchvision.datasets.ImageFolder.

    The training set gets the augmentation transform; the validation set
    gets the deterministic inference transform.

    Args:
        data_dir:   Root dataset directory containing class sub-folders.
        batch_size: Number of samples per mini-batch.

    Returns:
        tuple(train_loader, val_loader, dataset_size)
    """
    processor = ImageProcessor()

    # We need two separate dataset objects so each gets its own transform
    full_aug   = datasets.ImageFolder(data_dir, transform=processor.augmentation_transform)
    full_infer = datasets.ImageFolder(data_dir, transform=processor.inference_transform)

    dataset_size = len(full_aug)
    val_size     = int(dataset_size * VALIDATION_SPLIT)
    train_size   = dataset_size - val_size

    # Use the same random split indices for both (reproducibility)
    generator = torch.Generator().manual_seed(42)
    train_indices, val_indices = random_split(
        range(dataset_size), [train_size, val_size], generator=generator
    )

    train_subset = torch.utils.data.Subset(full_aug,   list(train_indices))
    val_subset   = torch.utils.data.Subset(full_infer, list(val_indices))

    train_loader = DataLoader(
        train_subset, batch_size=batch_size, shuffle=True,
        num_workers=0, pin_memory=False,
    )
    val_loader = DataLoader(
        val_subset, batch_size=batch_size, shuffle=False,
        num_workers=0, pin_memory=False,
    )

    print(
        f"\nData split: {train_size} training samples | "
        f"{val_size} validation samples"
    )
    return train_loader, val_loader, dataset_size


# -------------------------------------------------------------------
# STEP 3 — Model setup
# -------------------------------------------------------------------

def build_model(device: str):
    """
    Load a pretrained MobileNetV2, replace the classifier head for
    NUM_CLASSES outputs, optionally freeze the backbone, and move
    everything to *device*.

    Args:
        device: ``'cpu'`` or ``'cuda'``.

    Returns:
        tuple(model, optimizer, loss_fn, scheduler)
    """
    print("\nLoading pretrained MobileNetV2 …")
    model = models.mobilenet_v2(pretrained=True)
    model.classifier[1] = nn.Linear(1280, NUM_CLASSES)

    if FREEZE_BACKBONE:
        for param in model.features.parameters():
            param.requires_grad = False
        trainable_params = model.classifier.parameters()
        print("Backbone frozen — training classifier head only.")
    else:
        trainable_params = model.parameters()
        print("Full fine-tuning mode — all parameters trainable.")

    model = model.to(device)

    optimizer = torch.optim.Adam(trainable_params, lr=LEARNING_RATE)
    loss_fn   = nn.CrossEntropyLoss()
    scheduler = torch.optim.lr_scheduler.StepLR(
        optimizer, step_size=5, gamma=0.5
    )

    return model, optimizer, loss_fn, scheduler


# -------------------------------------------------------------------
# STEP 4 — Training loop
# -------------------------------------------------------------------

def train(model, train_loader, val_loader, optimizer, loss_fn, scheduler, device):
    """
    Run the full training loop for EPOCHS epochs.

    Per epoch:
      - Forward pass + backprop on training set.
      - Validation pass (no gradients) to compute loss and accuracy.
      - Save checkpoint when validation accuracy improves.
      - Step the LR scheduler.

    Args:
        model:        The MobileNetV2 model on *device*.
        train_loader: DataLoader for training samples.
        val_loader:   DataLoader for validation samples.
        optimizer:    Adam optimiser instance.
        loss_fn:      CrossEntropyLoss instance.
        scheduler:    StepLR scheduler instance.
        device:       ``'cpu'`` or ``'cuda'``.

    Returns:
        dict with training history statistics.
    """
    best_val_acc   = 0.0
    best_epoch     = 0
    history = {
        'train_losses': [],
        'val_losses':   [],
        'val_accs':     [],
    }

    print(f"\nStarting training for {EPOCHS} epoch(s) on {str(device).upper()}…\n")
    print("─" * 70)

    start_time = time.time()

    for epoch in range(1, EPOCHS + 1):

        # ── Training phase ────────────────────────────────────────────
        model.train()
        total_train_loss = 0.0

        for inputs, labels in train_loader:
            inputs, labels = inputs.to(device), labels.to(device)

            optimizer.zero_grad()
            outputs = model(inputs)
            loss    = loss_fn(outputs, labels)
            loss.backward()
            optimizer.step()

            total_train_loss += loss.item() * inputs.size(0)

        avg_train_loss = total_train_loss / len(train_loader.dataset)

        # ── Validation phase ──────────────────────────────────────────
        model.eval()
        total_val_loss = 0.0
        correct        = 0
        total          = 0

        with torch.no_grad():
            for inputs, labels in val_loader:
                inputs, labels = inputs.to(device), labels.to(device)
                outputs = model(inputs)
                loss    = loss_fn(outputs, labels)

                total_val_loss += loss.item() * inputs.size(0)
                preds    = torch.argmax(outputs, dim=1)
                correct += (preds == labels).sum().item()
                total   += labels.size(0)

        avg_val_loss = total_val_loss / len(val_loader.dataset) if len(val_loader.dataset) > 0 else 0.0
        val_acc      = (correct / total * 100) if total > 0 else 0.0

        history['train_losses'].append(avg_train_loss)
        history['val_losses'].append(avg_val_loss)
        history['val_accs'].append(val_acc)

        print(
            f"Epoch [{epoch:>2}/{EPOCHS}] | "
            f"Train Loss: {avg_train_loss:.4f} | "
            f"Val Loss: {avg_val_loss:.4f} | "
            f"Val Accuracy: {val_acc:.1f}%"
        )

        # ── Save best checkpoint ──────────────────────────────────────
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_epoch   = epoch
            torch.save(model.state_dict(), MODEL_SAVE_PATH)
            print(f"  ✓ Saved best model (accuracy: {val_acc:.1f}%)")

        scheduler.step()

    elapsed_minutes = (time.time() - start_time) / 60

    print("─" * 70)
    history['best_val_acc']     = best_val_acc
    history['best_epoch']       = best_epoch
    history['elapsed_minutes']  = elapsed_minutes
    history['final_train_loss'] = history['train_losses'][-1] if history['train_losses'] else 0.0
    history['final_val_loss']   = history['val_losses'][-1]   if history['val_losses']   else 0.0

    return history


# -------------------------------------------------------------------
# STEP 5 — Post-training summary and report
# -------------------------------------------------------------------

def print_summary(history: dict, dataset_size: int) -> None:
    """
    Print a human-readable training summary to stdout.

    Args:
        history:      Dict returned by :func:`train`.
        dataset_size: Total number of images in the dataset.
    """
    print(
        "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  Training Complete!\n"
        f"  Best Validation Accuracy : {history['best_val_acc']:.1f}%"
        f"  (epoch {history['best_epoch']})\n"
        f"  Model saved to           : {MODEL_SAVE_PATH}\n"
        f"  Total training time      : {history['elapsed_minutes']:.1f} minutes\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )


def save_report(history: dict, dataset_size: int) -> None:
    """
    Persist a JSON training report to ``training_report.json``.

    Args:
        history:      Dict returned by :func:`train`.
        dataset_size: Total image count used for training + validation.
    """
    report = {
        "epochs":                EPOCHS,
        "best_val_accuracy":     round(history['best_val_acc'], 4),
        "final_train_loss":      round(history['final_train_loss'], 6),
        "final_val_loss":        round(history['final_val_loss'], 6),
        "training_time_minutes": round(history['elapsed_minutes'], 2),
        "num_classes":           NUM_CLASSES,
        "class_names":           CLASS_NAMES,
        "dataset_size":          dataset_size,
        "freeze_backbone":       FREEZE_BACKBONE,
        "learning_rate":         LEARNING_RATE,
        "batch_size":            BATCH_SIZE,
        "device":                DEVICE,
        "timestamp":             datetime.now(timezone.utc).isoformat(),
    }

    report_path = 'training_report.json'
    with open(report_path, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, indent=2)

    print(f"Training report saved to {report_path}")


# -------------------------------------------------------------------
# STEP 6 — Entry point
# -------------------------------------------------------------------

def run_training_pipeline() -> None:
    """
    Execute the full training pipeline end-to-end.

    Steps
    -----
    1. Verify dataset.
    2. Build DataLoaders.
    3. Build model, optimiser, and scheduler.
    4. Train for EPOCHS epochs.
    5. Print summary and save JSON report.
    """
    print("=" * 60)
    print("  BhoomiFi — Crop Health CV Model Training")
    print("=" * 60)

    # 1. Verify dataset
    counts = verify_dataset(TRAINING_DATA_DIR)

    # 2. DataLoaders
    train_loader, val_loader, dataset_size = build_dataloaders(
        TRAINING_DATA_DIR, BATCH_SIZE
    )

    # 3. Model + optimiser
    device = torch.device(DEVICE)
    model, optimizer, loss_fn, scheduler = build_model(DEVICE)

    # 4. Train
    history = train(
        model, train_loader, val_loader,
        optimizer, loss_fn, scheduler, device,
    )

    # 5. Summary + report
    print_summary(history, dataset_size)
    save_report(history, dataset_size)


if __name__ == '__main__':
    try:
        run_training_pipeline()
    except FileNotFoundError as exc:
        print(f"\n[ERROR] {exc}")
        print("Hint: Create the training_images/ folder and add crop photos.")
    except RuntimeError as exc:
        print(f"\n[ERROR] {exc}")
    except KeyboardInterrupt:
        print("\nTraining interrupted by user.")
    except Exception as exc:
        print(f"\n[UNEXPECTED ERROR] {exc}")
        raise
