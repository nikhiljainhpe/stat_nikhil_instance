from trac.core import Component, implements
from trac.ticket.api import ITicketChangeListener

class TicketStatusLogger(Component):
    """Logs ticket status changes (with ticket ID and summary) to the Trac debug log."""
    implements(ITicketChangeListener)

    def ticket_created(self, ticket):
        pass

    def ticket_deleted(self, ticket):
        pass

    def ticket_changed(self, ticket, comment, author, old_values):
        self.log.info("Hello")
        if 'status' in old_values:
            old_status = old_values['status']
            new_status = ticket['status']
            summary = ticket['summary'] or '<no summary>'
            self.log.debug(
                f"TicketStatusLogger: ticket {ticket.id} '{summary}' status changed "
                f"from {old_status!r} to {new_status!r}"
            )