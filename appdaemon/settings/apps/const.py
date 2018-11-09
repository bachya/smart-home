"""Define various constants."""
BLACKOUT_START = '22:00:00'
BLACKOUT_END = '08:00:00'

PEOPLE = {
    'Aaron': {
        'car': 'device_tracker.2010_subaru_legacy',
        'device_tracker': 'device_tracker.aaron_iphone',
        'notifiers': ['ios_aaron_bachs_iphone'],
        'presence_manager_input_select': 'input_select.aaron_presence_status',
        'push_device_id': '885F47F4-56F2-435C-A84C-84654D0A906F'
    },
    'Britt': {
        'device_tracker': 'device_tracker.britt_iphone',
        'notifiers': ['ios_brittany_bachs_iphone'],
        'presence_manager_input_select': 'input_select.britt_presence_status',
        'push_device_id': '3CCFD32B-8C04-4A0D-94C2-6E934E8B6705'
    }
}

THRESHOLD_CLOUDY = 70.0
