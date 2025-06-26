#!/opt/stat/python3/bin/python3
# Copyright 2024 Hewlett Packard Enterprise Development LP.

import xmlrpc.client
import ssl
import json
import configparser
import os
import argparse
from datetime import datetime
from rich import print
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

console = Console()

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, xmlrpc.client.DateTime):
            return str(obj)
        return super().default(obj)

def human_readable_time(date_obj):
    if isinstance(date_obj, xmlrpc.client.DateTime):
        dt = datetime.strptime(str(date_obj), "%Y%m%dT%H:%M:%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return str(date_obj)

parser = argparse.ArgumentParser(description='View a Trac wiki page, list pages, or display a markdown file.')
parser.add_argument('wiki_page_name', nargs='?', default=None, help='The name of the wiki page to view')
parser.add_argument('-l', '--list', nargs='?', const='', metavar='STRING', help='List all available wiki pages or search by string')
parser.add_argument('-f', '--file', help='Display a markdown file from the filesystem')
args = parser.parse_args()

config = configparser.ConfigParser()
config_file_path = os.path.expanduser('~/.cartman/config')
config.read(config_file_path)

parts = config['trac']['base_url'].split('://', 1)
scheme = parts[0] + '://'
rest = parts[1]

trac_url = f"{scheme}{config['trac']['username']}:{config['trac']['password']}@{rest}/login/xmlrpc"

context = ssl._create_unverified_context()

server = xmlrpc.client.ServerProxy(trac_url, context=context)

try:
    if args.file:
        try:
            with open(args.file, 'r') as md_file:
                file_content = md_file.read()
                markdown = Markdown(file_content)
                console.print(markdown)
        except FileNotFoundError:
            console.print(f"[red]File not found: {args.file}[/red]")
        except Exception as e:
            console.print(f"[red]Error reading file: {e}[/red]")
    else:
        if args.list is not None:
            all_pages = server.wiki.getAllPages()

            search_string = args.list.strip().lower() if args.list else ''
            if search_string:
                all_pages = [page for page in all_pages if search_string in page.lower()]

            if not all_pages:
                console.print(f"[yellow]No wiki pages found matching '{search_string}'[/yellow]")
            else:
                table = Table(title="List of Wiki Pages", style="bold white on blue")
                table.add_column("Wiki Page Name", justify="left", style="cyan", no_wrap=True)

                for page in all_pages:
                    table.add_row(page)

                console.print(table)

        else:
            wiki_page_name = args.wiki_page_name or 'WikiStart'

            page_content = server.wiki.getPage(wiki_page_name)

            page_info = server.wiki.getPageInfo(wiki_page_name)

            page_info["lastModified"] = human_readable_time(page_info["lastModified"])

            table = Table.grid(expand=True)
            table.add_column(justify="left")
            table.add_column(justify="right")
            table.add_row(
                f"[bold]Wiki Page[/bold]: {wiki_page_name}",
                f"[bold]Last Modified[/bold]: {page_info['lastModified']}",
            )
            status_panel = Panel(table, style="bold white on blue")

            markdown = Markdown(page_content)

            console.print(status_panel)
            console.print(markdown)

except xmlrpc.client.Fault as e:
    console.print(f"[red]XML-RPC Fault: {e}[/red]")

except Exception as e:
    console.print(f"[red]Error: {e}[/red]")
