
class AuroraException(Exception):
    """Base class for all Aurora exceptions."""

    def __init__(self, message, *args, **kwargs):
        super(AuroraException, self).__init__(message, *args, **kwargs)
        self.message = message

    def __str__(self):
        return self.message

    def __repr__(self):
        return self.message
