// WFM System - Minimal JavaScript (No Form Interference)

// Flash Messages System (Essential)
class FlashMessages {
    constructor() {
        this.container = null;
    }

    init() {
        this.container = document.getElementById('flash-messages');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'flash-messages';
            this.container.className = 'fixed-top mt-3';
            this.container.style.zIndex = '9999';
            document.body.appendChild(this.container);
        }
    }

    show(message, type = 'info') {
        if (!this.container) this.init();
        
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show mx-3`;
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        this.container.appendChild(alert);
        
        setTimeout(() => {
            if (alert.parentNode) {
                alert.parentNode.removeChild(alert);
            }
        }, 5000);
    }
}

// Basic Utility Functions
function showTimesheet() {
    window.location.href = '/time/timecard';
}

function showProfile() {
    window.location.href = '/auth/profile';
}

function showHelp() {
    if (window.flashMessages) {
        window.flashMessages.show('Help documentation coming soon!', 'info');
    }
}

function toggleQuickActionsView() {
    const quickActions = document.getElementById('quick-actions-section');
    if (quickActions) {
        quickActions.style.display = quickActions.style.display === 'none' ? 'block' : 'none';
    }
}

function refreshTimeEntries() {
    // Simple page reload to refresh data
    window.location.reload();
}

// Initialize minimal functionality
document.addEventListener('DOMContentLoaded', function() {
    // Initialize flash messages only
    window.flashMessages = new FlashMessages();
    window.flashMessages.init();
    
    // Initialize Feather icons if available
    if (typeof feather !== 'undefined') {
        feather.replace();
    }
    
    console.log('Altron WFM System initialized successfully');
});