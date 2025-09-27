// Socket.IO client for real-time updates
const socket = io();

// Listen for crowd status updates
socket.on('crowd_update', function(data) {
    console.log('Crowd update received:', data);
    
    // Update crowd status elements
    const statusElements = document.querySelectorAll('#crowdStatus, #currentStatus, #latestStatus');
    const countElements = document.querySelectorAll('#currentCount, #latestCount');
    
    statusElements.forEach(element => {
        if (element) {
            if (element.id === 'currentStatus') {
                element.textContent = data.status;
                element.className = `badge bg-${data.status === 'Low' ? 'success' : data.status === 'Medium' ? 'warning' : 'danger'}`;
            } else {
                element.innerHTML = `Current Status: ${data.status}<br><small>People detected: ${data.count}</small>`;
            }
        }
    });
    
    countElements.forEach(element => {
        if (element) {
            element.textContent = `People detected: ${data.count}`;
        }
    });
    
    // Show notification for high crowd
    if (data.status === 'High') {
        showNotification('Temple Alert', 'High crowd detected! Estimated wait time: 30 mins', 'warning');
    }
});

// Listen for new bookings (admin dashboard)
socket.on('new_booking', function(data) {
    console.log('New booking received:', data);
    
    const bookingsTable = document.querySelector('#bookingsTable tbody');
    if (bookingsTable) {
        const newRow = `
            <tr class="table-success">
                <td>${data.id}</td>
                <td>${data.user}</td>
                <td>${data.date}</td>
                <td>${data.time_slot}</td>
                <td>${data.persons}</td>
                <td>${data.created_at}</td>
            </tr>
        `;
        bookingsTable.insertAdjacentHTML('afterbegin', newRow);
        
        // Remove highlight after 3 seconds
        setTimeout(() => {
            const newRowElement = bookingsTable.querySelector('tr.table-success');
            if (newRowElement) {
                newRowElement.classList.remove('table-success');
            }
        }, 3000);
        
        showNotification('New Booking', `${data.user} booked ${data.persons} persons for ${data.date}`, 'info');
    }
});

// Show browser notification
function showNotification(title, message, type = 'info') {
    // Browser notification
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(title, {
            body: message,
            icon: '/static/temple-icon.png'
        });
    }
    
    // Toast notification
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    toast.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 300px;';
    toast.innerHTML = `
        <strong>${title}:</strong> ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(toast);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    }, 5000);
}

// Request notification permission on page load
document.addEventListener('DOMContentLoaded', function() {
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }
});