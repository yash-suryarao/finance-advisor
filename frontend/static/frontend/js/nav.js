// nav.js - Global Navigation Handlers

// Fetch User Data from API
const navAuthHeaders = {
    "Authorization": `Bearer ${localStorage.getItem('access_token')}`
};

async function fetchUserProfile() {
    try {
        const response = await fetch('/users/api/user-profile/', { headers: navAuthHeaders });
        const data = await response.json();

        const avatarEl = document.getElementById('userAvatar');
        const nameEl = document.getElementById('userName');
        const dateEl = document.getElementById('currentDate');

        if (avatarEl) avatarEl.src = data.avatar;
        if (nameEl) nameEl.textContent = data.username;
        if (dateEl) dateEl.textContent = new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
    } catch (error) {
        console.error('Error fetching user profile:', error);
    }
}

// Toggle User Dropdown Menu
document.addEventListener('DOMContentLoaded', () => {
    fetchUserProfile();

    const userDropdownBtn = document.getElementById('userDropdownBtn');
    const userDropdown = document.getElementById('userDropdown');

    if (userDropdownBtn) {
        userDropdownBtn.addEventListener('click', () => {
            userDropdown.classList.toggle('hidden');
        });
    }

    // Close dropdown when clicking outside
    document.addEventListener('click', (event) => {
        if (userDropdownBtn && userDropdown && !userDropdownBtn.contains(event.target) && !userDropdown.contains(event.target)) {
            userDropdown.classList.add('hidden');
        }
    });
});
