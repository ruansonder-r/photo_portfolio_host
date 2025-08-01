def photographer_info(request):
    """Context processor to provide photographer information globally"""
    return {
        'PHOTOGRAPHER_NAME': 'Ruansonder_R',
        'PHOTOGRAPHER_EMAIL': 'ruansonder.r@gmail.com',
        'PHOTOGRAPHER_LOCATION': 'Cape Town, South Africa',
    } 
