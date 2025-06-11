// Altron WFM System - Minimal JavaScript (No Form Interference)

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

// Live Clock Timer (No fetch interference)
class LiveClockTimer {
    constructor() {
        this.timerElement = null;
        this.clockInTime = null;
        this.interval = null;
        this.isRunning = false;
    }

    init() {
        // Check for timer elements on different pages
        this.timerElement = document.getElementById('liveDuration') || document.getElementById('live-timer');
        if (this.timerElement) {
            this.checkClockStatus();
        }
    }

    checkClockStatus() {
        // Try dashboard format first
        const clockInTimeElement = document.getElementById('clockInTime');
        if (clockInTimeElement) {
            const isoTime = clockInTimeElement.getAttribute('data-iso-time');
            if (isoTime && isoTime !== '') {
                try {
                    this.clockInTime = new Date(isoTime);
                    this.startTimer();
                    return;
                } catch (error) {
                    console.log('Could not parse clock in time:', isoTime);
                }
            }
        }
        
        // Try timecard format - look for hidden clock-in time data
        const statusDisplay = document.getElementById('status-display');
        if (statusDisplay) {
            const clockInData = statusDisplay.getAttribute('data-clock-in-time');
            if (clockInData && clockInData !== '') {
                try {
                    this.clockInTime = new Date(clockInData);
                    this.startTimer();
                } catch (error) {
                    console.log('Could not parse timecard clock in time:', clockInData);
                }
            }
        }
    }

    startTimer() {
        if (this.interval) clearInterval(this.interval);
        
        this.isRunning = true;
        this.updateDisplay();
        this.interval = setInterval(() => this.updateDisplay(), 1000);
    }

    updateDisplay() {
        if (!this.timerElement || !this.clockInTime) return;
        
        const now = new Date();
        const diff = now - this.clockInTime;
        
        const hours = Math.floor(diff / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((diff % (1000 * 60)) / 1000);
        
        this.timerElement.textContent = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }

    onClockIn() {
        this.clockInTime = new Date();
        this.startTimer();
    }

    onClockOut() {
        if (this.interval) {
            clearInterval(this.interval);
            this.interval = null;
        }
        this.isRunning = false;
        if (this.timerElement) {
            this.timerElement.textContent = '00:00:00';
        }
    }

    destroy() {
        if (this.interval) {
            clearInterval(this.interval);
        }
    }
}

// Initialize minimal functionality
document.addEventListener('DOMContentLoaded', function() {
    // Initialize flash messages
    window.flashMessages = new FlashMessages();
    window.flashMessages.init();
    
    // Initialize live timer
    window.liveTimer = new LiveClockTimer();
    window.liveTimer.init();
    
    // Initialize Feather icons if available
    if (typeof feather !== 'undefined') {
        feather.replace();
    }
    
    console.log('Altron WFM System initialized successfully');
});

// Clean up on page unload
window.addEventListener('beforeunload', function() {
    if (window.liveTimer) {
        window.liveTimer.destroy();
    }
});