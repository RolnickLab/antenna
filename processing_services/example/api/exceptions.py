"""
Define custom exceptions for various algorithm task types.
"""


class LocalizationError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message

    def __str__(self):
        return f'{self.__class__.__name__}("{self.message}")'


class ClassificationError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message

    def __str__(self):
        return f'{self.__class__.__name__}("{self.message}")'


class DetectionError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message

    def __str__(self):
        return f'{self.__class__.__name__}("{self.message}")'
