"""Domain errors, raised by services and by the models that enforce locking."""


class BillingError(Exception):
    """Base for every refusal this app makes."""


class DocumentLocked(BillingError):
    """An issued document was edited or deleted.

    Issued documents are immutable: the number has to keep identifying a fixed
    document. The exit for a wrong invoice is cancel-and-reissue, not an edit.
    """


class AlreadyIssued(BillingError):
    """Issue was called on a document that already has a number."""


class NotConvertible(BillingError):
    """A quote was converted when it was not in a state to be."""
