from __future__ import annotations

__all__ = (
    'InfinitodeError',
    'APIError',
    'BadArgument',
)


class InfinitodeError(Exception):
    '''Base Infinitode Error.'''
    pass


class APIError(InfinitodeError):
    '''Error directly related to the communication with the API.'''
    pass


class BadArgument(InfinitodeError):
    '''Error raised when an invalid argument is passed.'''
    pass
