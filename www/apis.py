# -*- coding: utf-8 -*-
# @author xian_wen
# @date 6/1/2021 7:48 PM

class APIError(Exception):
    """
    The base APIError which contains error(required), data(optional) and message(optional).
    """

    def __init__(self, error, data='', message=''):
        super().__init__(message)
        self.error = error
        self.data = data
        self.message = message


class APIValueError(APIError):
    """
    Indicate the input value has error or is invalid. The data specifies the error field of input form.
    """

    def __init__(self, field, message=''):
        super().__init__('Value: invalid', field, message)


class APIResourceNotFoundError(APIError):
    """
    Indicate the resource was not found. The data specifies the resource name.
    """

    def __init__(self, field, message=''):
        super().__init__('Value: not found', field, message)


class APIPermissionError(APIError):
    """
    Indicate the api has no permission.
    """

    def __init__(self, message=''):
        super().__init__('Permission: forbidden', 'permission', message)
