import subprocess
from trac.core import Component, implements
from trac.ticket.api import ITicketChangeListener
from trac.wiki.api import IWikiChangeListener
from trac.versioncontrol.api import IRepositoryChangeListener
from trac.config import Option

class EmailNotifier(Component):
    implements(ITicketChangeListener, IWikiChangeListener, IRepositoryChangeListener)

    email_sender = Option('email', 'sender', '', doc="The sender email address")
    email_recipient = Option('email', 'recipient', '', doc="The recipient email address")

    def send_email(self, subject, message):
        if not self.email_sender or not self.email_recipient:
            self.log.error("Sender or recipient email address not configured.")
            return

        email_message = f"From: {self.email_sender}\nTo: {self.email_recipient}\nSubject: {subject}\n\n{message}"

        try:
            process = subprocess.Popen(['/usr/sbin/sendmail', '-t', '-oi'], stdin=subprocess.PIPE)
            process.communicate(email_message.encode('utf-8'))
        except Exception as e:
            self.log.error(f"Error sending email: {e}")

    def format_changes(self, ticket, old_values):
        """Format the changes to display old and new values generically."""
        if not old_values:
            return ""

        changes = []
        for field, old_value in old_values.items():
            new_value = ticket[field]  # Get the new value from the ticket
            changes.append(f"- **{field}**: {old_value} → {new_value}")
        
        return "\n".join(changes)

    # Implement the required methods for ITicketChangeListener, IWikiChangeListener, IRepositoryChangeListener
    def ticket_created(self, ticket):
        message = self.format_changes(ticket, None)
        self.send_email("Ticket Created", message)

    def ticket_changed(self, ticket, comment, author, old_values):
        message = self.format_changes(ticket, old_values)
        self.send_email("Ticket Changed", message)

    def ticket_deleted(self, ticket):
        self.send_email("Ticket Deleted", f"Ticket {ticket.id} has been deleted.")

    def wiki_page_added(self, page):
        self.send_email("Wiki Page Added", f"Wiki page {page.name} has been added.")

    def wiki_page_changed(self, page, version, t, comment, author, ipnr):
        self.send_email("Wiki Page Changed", f"Wiki page {page.name} has been changed.")

    def wiki_page_deleted(self, page):
        self.send_email("Wiki Page Deleted", f"Wiki page {page.name} has been deleted.")

    def repository_changed(self, repos, changeset):
        self.send_email("Repository Changed", f"Repository {repos.name} has been changed.")
