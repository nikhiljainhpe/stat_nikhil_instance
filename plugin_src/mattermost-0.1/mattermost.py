# Copyright 2024 Hewlett Packard Enterprise Development LP.

import json
import requests
from trac.core import Component, implements
from trac.ticket.api import ITicketChangeListener
from trac.wiki.api import IWikiChangeListener
from trac.versioncontrol.api import IRepositoryChangeListener
from trac.config import Option

class MattermostNotifier(Component):
    implements(ITicketChangeListener, IWikiChangeListener, IRepositoryChangeListener)

    mattermost_api_url = Option('mattermost', 'api_url', '', doc="The Mattermost API URL")
    mattermost_token = Option('mattermost', 'token', '', doc="The Mattermost token")
    mattermost_channel_id = Option('mattermost', 'channel_id', '', doc="The Mattermost channel ID")

    def send_to_mattermost(self, message):
        if not self.mattermost_api_url or not self.mattermost_token or not self.mattermost_channel_id:
            self.log.error("Mattermost API URL, token, or channel ID not configured.")
            return

        headers = {
            'Authorization': f'Bearer {self.mattermost_token}',
            'Content-Type': 'application/json'
        }

        payload = {
            'channel_id': self.mattermost_channel_id,
            'message': message
        }

        try:
            response = requests.post(f'{self.mattermost_api_url}/api/v4/posts', data=json.dumps(payload), headers=headers)
            if response.status_code != 201:
                self.log.error(f"Failed to send message to Mattermost: {response.status_code}, {response.text}")
        except Exception as e:
            self.log.error(f"Error sending message to Mattermost: {e}")

    def format_changes(self, ticket, old_values):
        """Format the changes to display old and new values generically."""
        if not old_values:
            return ""

        changes = []
        for field, old_value in old_values.items():
            new_value = ticket[field]  # Get the new value from the ticket
            changes.append(f"- **{field}**: {old_value} → {new_value}")
        
        return "\n".join(changes)

    def ticket_created(self, ticket):
        message = f"**New ticket created: #{ticket.id} - {ticket['summary']} by {ticket['reporter']}**"
        self.send_to_mattermost(message)
        ticket._created = True  # Mark ticket as created to avoid duplicate updates.

    def ticket_changed(self, ticket, comment, author, old_values):
        if hasattr(ticket, '_created') and ticket._created:
            return

        message = f"**Ticket #{ticket.id} updated by {author}**\n"

        # Only add the comment line if the comment is not empty
        if comment and comment.strip():
            message += f"Comment: {comment}\n"

        # Show any field changes
        changes = self.format_changes(ticket, old_values)
        if changes:
            message += f"Changes:\n{changes}"

        self.send_to_mattermost(message)

    def ticket_deleted(self, ticket):
        message = f"**Ticket #{ticket.id} deleted.**"
        self.send_to_mattermost(message)

    def wiki_page_added(self, page):
        message = f"**New wiki page created: {page.name} by {page.author}**"
        self.send_to_mattermost(message)

    def wiki_page_changed(self, page, version, t, comment, author):
        message = f"**Wiki page {page.name} updated by {author}**\n"
        
        if comment:
            message += f"Comment: {comment}\n"
        
        self.send_to_mattermost(message)

    def wiki_page_deleted(self, page):
        message = f"**Wiki page {page.name} deleted.**"
        self.send_to_mattermost(message)

    def wiki_page_version_deleted(self, page):
        message = f"**Version of wiki page {page.name} deleted.**"
        self.send_to_mattermost(message)

    def changeset_added(self, repos, changeset):
        message = f"**New changeset added: {changeset.rev} by {changeset.author}**"
        self.send_to_mattermost(message)

    def changeset_modified(self, repos, changeset, old_changeset):
        message = f"**Changeset {changeset.rev} modified by {changeset.author}**"
        self.send_to_mattermost(message)
