from __future__ import annotations

# packages
from discord.ext.commands import BadArgument, CheckFailure


class BadLevel(BadArgument):
    """Exception raised when the provided level is not valid."""

    def __init__(self, message: str = 'The provided level is invalid.') -> None:
        super().__init__(message)


class BadChannel(CheckFailure):
    """Exception raised when the message channel is not an allowed channel."""

    def __init__(self, message: str = 'Command used in wrong channel.') -> None:
        super().__init__(message)


class TagError(RuntimeError):
    """Raised for tag errors that should be replied to the user."""
    pass


class InCommandError(Exception):
    """Exception raised when an error occurs in a command."""
    pass


class InvalidDateError(InCommandError):
    """Exception raised when an invalid date is provided."""

    def __init__(self, message: str = 'Could not find anything for that date, sorry.') -> None:
        self.log: str = 'Invalid date provided.'
        super().__init__(message)


class NoPlayerProvidedError(InCommandError):
    """Exception raised when no player is provided."""

    def __init__(self, message: str = 'Provide a player to search for.') -> None:
        self.log: str = 'No player provided.'
        super().__init__(message)


class InvalidPlayerError(InCommandError):
    """Exception raised when an invalid player is provided."""

    def __init__(self, message: str = 'Could not find player. Check for spelling mistakes or try using '
                 'the U- playerid from your profile page (Top left in the main menu).') -> None:
        self.log: str = 'Invalid player provided.'
        super().__init__(message)


class NoPlayerError(InCommandError):
    """Raised when the bot is not in a voice channel."""

    def __init__(self, message: str = 'The bot is not in a voice channel.') -> None:
        super().__init__(message)


class NotInVoiceChannelError(InCommandError):
    """Raised when the user is not in a voice channel."""

    def __init__(self, message: str = 'You must be in a voice channel in order to use this command!') -> None:
        self.log: str = 'User is not in a voice channel.'
        super().__init__(message)


class PlayerNotConnectedError(InCommandError):
    """Raised when the player is not connected."""

    def __init__(self, message: str = 'The player is not connected.') -> None:
        super().__init__(message)


class NoTrackPlayingError(InCommandError):
    """Raised when no track is currently playing."""

    def __init__(self, message: str = 'No track is currently playing.') -> None:
        super().__init__(message)


class QueueEmptyError(InCommandError):
    """Raised when the queue is empty."""

    def __init__(self, message: str = 'The queue is empty.') -> None:
        super().__init__(message)


class QueueTooShortError(InCommandError):
    """Raised when the queue is too short."""

    def __init__(self, message: str = 'Queue is not long enough to skip to that index.') -> None:
        self.log: str = 'Queue is too short.'
        super().__init__(message)


class IndexTooSmallError(InCommandError):
    """Raised when the index is too small."""

    def __init__(self, message: str = 'The index must be >= 1.') -> None:
        super().__init__(message)


class AlreadyPausedError(InCommandError):
    """Raised when the player is already paused."""

    def __init__(self, message: str = 'The player is already paused.') -> None:
        super().__init__(message)


class NotPausedError(InCommandError):
    """Raised when the player is not paused."""

    def __init__(self, message: str = 'The player is not paused.') -> None:
        super().__init__(message)


class NotPrivilegedError(InCommandError):
    """Raised when the user is not privileged."""

    def __init__(self, action: str, *, end: bool = False) -> None:
        msg = f'Only the original requester may '
        msg += f'{action} the player.' if not end else action
        self.log = f'Not privileged to {action}.'
        super().__init__(msg)


class InvalidTimeError(InCommandError):
    """Raised when the time is invalid."""

    def __init__(self, message: str = 'The provided time is invalid.') -> None:
        super().__init__(message)
