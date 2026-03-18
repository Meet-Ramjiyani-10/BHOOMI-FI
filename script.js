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

messageInput.addEventListener("input", function() {
    const currentLength = this.value.length;
    counterDisplay.textContent = currentLength + " / 200 characters";
    
    // Color logic
    if (currentLength > 180) {
        counterDisplay.style.color = "red";
    } else if (currentLength > 150) {
        counterDisplay.style.color = "orange";
    } else {
        counterDisplay.style.color = "var(--text-light)";
    }
});
