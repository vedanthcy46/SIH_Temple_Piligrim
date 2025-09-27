// Shared data initialization for Temple Management System
(function() {
    // Initialize sample bookings if not exists
    if (!localStorage.getItem('templeBookings')) {
        const sampleBookings = [
            {
                id: 'TPL1001',
                name: 'Rajesh Kumar',
                date: '2024-01-15',
                timeSlot: '10:00-12:00',
                persons: '4',
                contact: '9876543210',
                status: 'Confirmed',
                timestamp: new Date().toISOString()
            },
            {
                id: 'TPL1002',
                name: 'Priya Sharma',
                date: '2024-01-15',
                timeSlot: '14:00-16:00',
                persons: '2',
                contact: '9876543211',
                status: 'Pending',
                timestamp: new Date().toISOString()
            },
            {
                id: 'TPL1003',
                name: 'Amit Patel',
                date: '2024-01-16',
                timeSlot: '6:00-8:00',
                persons: '6',
                contact: '9876543212',
                status: 'Confirmed',
                timestamp: new Date().toISOString()
            }
        ];
        localStorage.setItem('templeBookings', JSON.stringify(sampleBookings));
    }
    
    // Initialize crowd status if not exists
    if (!localStorage.getItem('crowdStatus')) {
        localStorage.setItem('crowdStatus', 'Medium');
    }
})();