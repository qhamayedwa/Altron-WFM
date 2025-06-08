// Main JavaScript for Flask PostgreSQL App

// Database status checker
class DatabaseStatus {
    constructor() {
        this.statusIndicator = document.getElementById('db-status');
        this.statusText = document.getElementById('db-status-text');
        this.init();
    }

    init() {
        if (this.statusIndicator) {
            this.checkStatus();
            // Check status every 30 seconds
            setInterval(() => this.checkStatus(), 30000);
        }
    }

    async checkStatus() {
        try {
            this.setStatus('loading', 'Checking...');
            
            const response = await fetch('/api/v1/db-status');
            const data = await response.json();
            
            if (response.ok && data.status === 'connected') {
                this.setStatus('connected', 'Connected');
                this.updateTableCounts(data.tables);
            } else {
                this.setStatus('error', 'Error');
                console.error('Database status error:', data.message);
            }
        } catch (error) {
            this.setStatus('error', 'Error');
            console.error('Failed to check database status:', error);
        }
    }

    setStatus(status, text) {
        if (this.statusIndicator) {
            this.statusIndicator.className = `db-status ${status}`;
        }
        if (this.statusText) {
            this.statusText.textContent = text;
        }
    }

    updateTableCounts(tables) {
        // Update count displays if they exist
        Object.entries(tables).forEach(([table, count]) => {
            const element = document.getElementById(`${table}-count`);
            if (element) {
                element.textContent = count;
            }
        });
    }
}

// Flash message handler
class FlashMessages {
    constructor() {
        this.init();
    }

    init() {
        // Auto-dismiss flash messages after 5 seconds
        const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(alert => {
            setTimeout(() => {
                const bsAlert = new bootstrap.Alert(alert);
                if (bsAlert) {
                    bsAlert.close();
                }
            }, 5000);
        });
    }

    show(message, type = 'info') {
        const alertContainer = document.getElementById('flash-messages');
        if (!alertContainer) return;

        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        alertContainer.appendChild(alertDiv);

        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alertDiv);
            if (bsAlert) {
                bsAlert.close();
            }
        }, 5000);
    }
}

// Sample data creator
class SampleDataManager {
    constructor() {
        this.button = document.getElementById('create-sample-data');
        this.init();
    }

    init() {
        if (this.button) {
            this.button.addEventListener('click', (e) => {
                e.preventDefault();
                this.createSampleData();
            });
        }
    }

    async createSampleData() {
        try {
            this.button.disabled = true;
            this.button.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating...';

            const response = await fetch('/create-sample-data');
            const data = await response.json();

            if (response.ok) {
                flashMessages.show(data.message, 'success');
                // Refresh page after 2 seconds to show new data
                setTimeout(() => window.location.reload(), 2000);
            } else {
                flashMessages.show(data.message, 'danger');
            }
        } catch (error) {
            console.error('Error creating sample data:', error);
            flashMessages.show('Failed to create sample data', 'danger');
        } finally {
            this.button.disabled = false;
            this.button.innerHTML = 'Create Sample Data';
        }
    }
}

// Loading states for forms
class LoadingManager {
    static showLoading(element) {
        element.classList.add('loading');
        const buttons = element.querySelectorAll('button[type="submit"]');
        buttons.forEach(btn => {
            btn.disabled = true;
            const originalText = btn.textContent;
            btn.setAttribute('data-original-text', originalText);
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Loading...';
        });
    }

    static hideLoading(element) {
        element.classList.remove('loading');
        const buttons = element.querySelectorAll('button[type="submit"]');
        buttons.forEach(btn => {
            btn.disabled = false;
            const originalText = btn.getAttribute('data-original-text');
            if (originalText) {
                btn.textContent = originalText;
            }
        });
    }
}

// Utility functions
const utils = {
    // Format date for display
    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },

    // Debounce function for search inputs
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    // Copy text to clipboard
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (err) {
            console.error('Failed to copy text:', err);
            return false;
        }
    }
};

// Live Clock Timer
class LiveClockTimer {
    constructor() {
        this.timerInterval = null;
        this.clockInTime = null;
        this.init();
    }

    init() {
        // Check if user is currently clocked in and start timer
        this.checkClockStatus();
        
        // Update timer every second
        this.startTimer();
    }

    async checkClockStatus() {
        try {
            const response = await fetch('/time/status');
            const data = await response.json();
            
            if (data.success && data.data.is_clocked_in && data.data.clock_in_time) {
                // Parse the clock-in time
                this.clockInTime = new Date(data.data.clock_in_time);
                this.updateDisplay();
            }
        } catch (error) {
            console.error('Failed to check clock status:', error);
        }
    }

    startTimer() {
        // Clear any existing timer
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
        }

        // Update every second
        this.timerInterval = setInterval(() => {
            this.updateDisplay();
        }, 1000);
    }

    updateDisplay() {
        const durationElement = document.getElementById('liveDuration');
        
        if (!durationElement || !this.clockInTime) {
            return;
        }

        const now = new Date();
        const elapsed = now - this.clockInTime;
        
        // Calculate hours, minutes, seconds
        const hours = Math.floor(elapsed / (1000 * 60 * 60));
        const minutes = Math.floor((elapsed % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((elapsed % (1000 * 60)) / 1000);

        // Format as HH:MM:SS
        const formattedTime = 
            `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        
        durationElement.textContent = formattedTime;
        
        // Add pulsing effect for active status
        durationElement.style.animation = 'pulse 2s infinite';
    }

    onClockIn() {
        // Set clock-in time to now
        this.clockInTime = new Date();
        this.updateDisplay();
    }

    onClockOut() {
        // Clear timer when clocked out
        this.clockInTime = null;
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
        }
    }

    destroy() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
        }
    }
}

// Time Tracking Functions
window.performClockIn = async function() {
    console.log('Performing clock in - updated function v2');
    const button = document.getElementById('clockInBtn');
    if (button) {
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Clocking In...';
    }
    
    try {
        const response = await fetch('/time/clock-in', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'same-origin',
            body: JSON.stringify({})  // Send empty JSON object instead of no body
        });
        
        console.log('Response status:', response.status);
        console.log('Response ok:', response.ok);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Response data:', data);
        
        if (data.success) {
            // Refresh the page to show updated status
            console.log('Clock in successful, reloading page');
            window.location.reload();
        } else {
            alert('Error: ' + data.message);
            if (button) {
                button.disabled = false;
                button.innerHTML = '<i data-feather="clock" class="me-2"></i>Clock In<small class="d-block">Start your workday</small>';
            }
        }
    } catch (error) {
        console.error('Clock in error:', error);
        console.error('Error details:', error.message, error.stack);
        alert('Failed to clock in. Please try again.');
        if (button) {
            button.disabled = false;
            button.innerHTML = '<i data-feather="clock" class="me-2"></i>Clock In<small class="d-block">Start your workday</small>';
        }
    }
};

window.clockIn = async function() {
    console.log('Clock in function called');
    try {
        const button = document.getElementById('clockInBtn');
        if (button) {
            button.disabled = true;
            button.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Clocking In...';
        }

        const response = await fetch('/time/clock-in', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        const data = await response.json();

        if (data.success) {
            // Update UI to show clocked in state
            updateClockButtonUI(true, data.clock_in_time);
            
            // Initialize live timer
            if (window.liveTimer) {
                window.liveTimer.onClockIn();
            }
            
            flashMessages.show('Successfully clocked in!', 'success');
            
            // Refresh time entries
            refreshTimeEntries();
        } else {
            flashMessages.show(data.message || 'Failed to clock in', 'danger');
        }
    } catch (error) {
        console.error('Clock in error:', error);
        flashMessages.show('Error clocking in. Please try again.', 'danger');
    } finally {
        // Reset button state
        const button = document.getElementById('clockInBtn');
        if (button) {
            button.disabled = false;
            button.innerHTML = '<i data-feather="clock" class="me-2"></i>Clock In<small class="d-block">Start your workday</small>';
            feather.replace();
        }
    }
}

window.clockOut = async function() {
    console.log('Clock out function called');
    try {
        const button = document.getElementById('clockOutBtn');
        if (button) {
            button.disabled = true;
            button.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Clocking Out...';
        }

        const response = await fetch('/time/clock-out', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        const data = await response.json();

        if (data.success) {
            // Update UI to show clocked out state
            updateClockButtonUI(false);
            
            // Stop live timer
            if (window.liveTimer) {
                window.liveTimer.onClockOut();
            }
            
            flashMessages.show('Successfully clocked out!', 'success');
            
            // Refresh time entries
            if (typeof refreshTimeEntries === 'function') {
                refreshTimeEntries();
            }
        } else {
            flashMessages.show(data.message || 'Failed to clock out', 'danger');
        }
    } catch (error) {
        console.error('Clock out error:', error);
        flashMessages.show('Error clocking out. Please try again.', 'danger');
    } finally {
        // Reset button state
        const button = document.getElementById('clockOutBtn');
        if (button) {
            button.disabled = false;
            button.innerHTML = '<i data-feather="clock" class="me-2"></i>Clock Out<small class="d-block" id="clockInTime">Started: Unknown</small><div class="live-timer mt-1"><strong class="text-white" id="liveDuration">00:00:00</strong><small class="d-block opacity-75">Working Time</small></div>';
            feather.replace();
        }
    }
}

function updateClockButtonUI(isClockedIn, clockInTime = null) {
    const container = document.getElementById('clockButtonContainer');
    if (!container) return;

    if (isClockedIn && clockInTime) {
        const formattedTime = new Date(clockInTime).toLocaleTimeString();
        container.innerHTML = `
            <button class="btn btn-danger w-100 mb-2" onclick="clockOut()" id="clockOutBtn">
                <i data-feather="clock" class="me-2"></i>Clock Out
                <small class="d-block" id="clockInTime">Started: ${formattedTime}</small>
                <div class="live-timer mt-1">
                    <strong class="text-white" id="liveDuration">00:00:00</strong>
                    <small class="d-block opacity-75">Working Time</small>
                </div>
            </button>
        `;
    } else {
        container.innerHTML = `
            <button class="btn btn-success w-100 mb-2" onclick="clockIn()" id="clockInBtn">
                <i data-feather="clock" class="me-2"></i>Clock In
                <small class="d-block">Start your workday</small>
            </button>
        `;
    }
    
    // Re-initialize feather icons
    if (typeof feather !== 'undefined') {
        feather.replace();
    }
}

// Time Entries Management
async function refreshTimeEntries() {
    const refreshBtn = document.getElementById('refreshBtn');
    const container = document.getElementById('timeEntriesContainer');
    
    if (refreshBtn) {
        refreshBtn.disabled = true;
        refreshBtn.innerHTML = '<i data-feather="refresh-cw" style="width: 16px; height: 16px;" class="spin"></i>';
    }
    
    try {
        const response = await fetch('/api/v1/recent-time-entries');
        const data = await response.json();
        
        if (data.success && data.data) {
            updateTimeEntriesTable(data.data);
        }
    } catch (error) {
        console.error('Failed to refresh time entries:', error);
    } finally {
        if (refreshBtn) {
            refreshBtn.disabled = false;
            refreshBtn.innerHTML = '<i data-feather="refresh-cw" style="width: 16px; height: 16px;"></i>';
            feather.replace();
        }
    }
}

function updateTimeEntriesTable(entries) {
    const container = document.getElementById('timeEntriesContainer');
    if (!container || !entries.length) return;
    
    const tableHtml = `
        <div class="table-responsive">
            <table class="table table-sm" id="timeEntriesTable">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Clock In</th>
                        <th>Clock Out</th>
                        <th>Hours</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${entries.map(entry => `
                        <tr>
                            <td>${new Date(entry.date).toLocaleDateString()}</td>
                            <td>${new Date(entry.clock_in_time).toLocaleTimeString()}</td>
                            <td>${entry.clock_out_time ? new Date(entry.clock_out_time).toLocaleTimeString() : 'Working'}</td>
                            <td>${entry.total_hours || '0.0'} hrs</td>
                            <td>
                                <span class="badge bg-${entry.status === 'approved' ? 'success' : entry.status === 'pending' ? 'warning' : 'secondary'}">
                                    ${entry.status}
                                </span>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
    
    container.innerHTML = tableHtml;
}

// Quick Action Functions
function showTimesheet() {
    window.location.href = '/time-entries';
}

function showProfile() {
    window.location.href = '/auth/profile';
}

function showHelp() {
    flashMessages.show('Help documentation is available in the user manual. Contact your system administrator for assistance.', 'info');
}

function toggleQuickActionsView() {
    const grid = document.getElementById('quickActionsGrid');
    const icon = document.getElementById('viewToggleIcon');
    
    if (grid && icon) {
        grid.classList.toggle('expanded');
        // Toggle between grid and list view icons
        const isExpanded = grid.classList.contains('expanded');
        icon.setAttribute('data-feather', isExpanded ? 'list' : 'grid');
        feather.replace();
    }
}

// Initialize components when DOM is loaded
let dbStatus, flashMessages, sampleDataManager, liveTimer;

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM Content Loaded - Initializing components');
    
    // Initialize components
    dbStatus = new DatabaseStatus();
    flashMessages = new FlashMessages();
    sampleDataManager = new SampleDataManager();
    
    // Initialize live timer for clock tracking
    window.liveTimer = new LiveClockTimer();

    // Add fade-in animation to main content
    const mainContent = document.querySelector('main');
    if (mainContent) {
        mainContent.classList.add('fade-in');
    }

    // Initialize feather icons
    if (typeof feather !== 'undefined') {
        feather.replace();
    }

    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(popoverTriggerEl => new bootstrap.Popover(popoverTriggerEl));
    
    // Test button functionality
    const clockInBtn = document.getElementById('clockInBtn');
    if (clockInBtn) {
        console.log('Clock in button found, adding event listener');
        clockInBtn.addEventListener('click', function(e) {
            e.preventDefault();
            console.log('Clock in button clicked via event listener');
            window.clockIn();
        });
    }
    
    console.log('Initialization complete');
});

// Global error handler
window.addEventListener('error', function(e) {
    console.error('Global error:', e.error);
});

// Global unhandled promise rejection handler
window.addEventListener('unhandledrejection', function(e) {
    console.error('Unhandled promise rejection:', e.reason);
});
