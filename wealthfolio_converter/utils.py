from logging import Logger, StreamHandler, Formatter

class WFLogger(Logger):
    """Base logging class to be passed into other classes."""

    def init(self) -> None:
        """Instantiate class-specific logging"""
        h = StreamHandler()
        f = Formatter(
            "{levelname:s} - {filename:s}:{lineno:d} ({funcName:s}) - {message:s}",
            style="{",
        )
        h.setFormatter(f)
        self.addHandler(h)
