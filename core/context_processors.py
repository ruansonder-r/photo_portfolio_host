def photographer_info(request):
    """Context processor to provide photographer information globally"""
    return {
        'PHOTOGRAPHER_NAME': 'Ruansonder_R',
        'PHOTOGRAPHER_EMAIL': 'photographer@example.com',
        'PHOTOGRAPHER_LOCATION': 'Your City, State',
    } 
