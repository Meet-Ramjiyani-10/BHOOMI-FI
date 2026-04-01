// Navbar shadow effect on scroll
window.addEventListener('scroll', () => {
    const navbar = document.getElementById('navbar');
    if (window.scrollY > 10) {
        navbar.classList.add('scrolled');
    } else {
        navbar.classList.remove('scrolled');
    }
});

// Smooth scrolling for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const targetId = this.getAttribute('href');
        if (targetId === '#') return;
        
        const targetElement = document.querySelector(targetId);
        if (targetElement) {
            const headerOffset = 70;
            const elementPosition = targetElement.getBoundingClientRect().top;
            const offsetPosition = elementPosition + window.pageYOffset - headerOffset;

            window.scrollTo({
                    top: offsetPosition,
                    behavior: "smooth"
            });
        }
    });
});

// Live character counter for textarea
const messageInput = document.getElementById("message");
const counterDisplay = document.getElementById("counter");

if (messageInput && counterDisplay) {
    messageInput.addEventListener("input", function() {
        const currentLength = this.value.length;
        counterDisplay.textContent = currentLength + " / 200 characters";
        
        if (currentLength > 180) {
            counterDisplay.style.color = "red";
        } else if (currentLength > 150) {
            counterDisplay.style.color = "orange";
        } else {
            counterDisplay.style.color = "var(--text-light)";
        }
    });
}

// Popup Form Functions
function openForm() {
    document.getElementById('popupOverlay').style.display = 'flex';
}

function closeForm() {
    document.getElementById('popupOverlay').style.display = 'none';
}

function generateScore() {
    const cropType = document.getElementById('popupCropType').value;
    const landSize = parseFloat(document.getElementById('popupLandSize').value);
    const location = document.getElementById('popupLocation').value;

    if (!cropType || !landSize || !location) {
        alert('Please fill in all fields');
        return;
    }

    // Simple score calculation: land * 5 + random(0-20)
    const randomBonus = Math.floor(Math.random() * 21);
    let score = Math.round(landSize * 5 + randomBonus);
    
    // Cap score at 100
    if (score > 100) score = 100;

    // Store data in localStorage
    localStorage.setItem('farmerData', JSON.stringify({
        cropType: cropType,
        landSize: landSize,
        location: location,
        harvestScore: score
    }));

    alert('Your Harvest Score: ' + score);
    window.location.href = 'dashboard.html';
}
