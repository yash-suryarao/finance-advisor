document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll('.logout-btn').forEach(logoutBtn => {
        logoutBtn.addEventListener("click", async (e) => {
            e.preventDefault();
            const authHeaders = {
                "Authorization": `Bearer ${localStorage.getItem('access_token')}`
            };
            try {
                await fetch('/users/logout/', {
                    method: 'POST',
                    headers: {
                        "Content-Type": "application/json",
                        ...authHeaders
                    },
                    body: JSON.stringify({ refresh_token: localStorage.getItem('refresh_token') })
                });
            } catch (error) {
                console.error("Error during logout", error);
            }

            // Always clear tokens locally and redirect
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            window.location.href = "/login/";
        });
    });
});
