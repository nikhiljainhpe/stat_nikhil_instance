# Copyright 2024 Hewlett Packard Enterprise Development LP.

from trac.core import *
from trac.ticket.api import ITicketChangeListener
from trac.attachment import Attachment

import requests
import json
import os
import io

url_base = 'https://127.0.0.1:8080/cmu/v1/'
aliasurl = url_base+"systemgroups/compute?fields=nodes.name,nodes.aliases"
session_key_file = '/opt/stat/.session_key'

class StatHpcmDbPlugin(Component):
    implements(ITicketChangeListener)
    
    def __init__(self): 
        self.log.debug("HPCMDB, in StatHpcmDbPlugin")
    
    def ticket_changed(self, ticket, comment, author, old_values):

        if 'hostname' in old_values and not ticket['xname']:
            xname_value = self._hpcm_get_xname(ticket['hostname'])
            if xname_value:
                ticket['xname']=xname_value
                ticket.save_changes()

        if 'xname' in old_values and not ticket['hostname']:
            node_value = self._hpcm_get_node(ticket['xname'])
            if node_value:
                ticket['hostname']=node_value
                ticket.save_changes()
    

    def ticket_created(self, ticket):

        if ticket['hostname'] and not ticket['xname']:
            xname_value = self._hpcm_get_xname(ticket['hostname'])
            if xname_value :
                ticket['xname'] = xname_value
                ticket.save_changes()
                data=self._hpcm_db_inventory(ticket['hostname'])

        if ticket['xname'] and not ticket['hostname']:
            node_value = self._hpcm_get_node(ticket['xname'])
            if node_value: 
                ticket['hostname'] = node_value
                ticket.save_changes()
                data=self._hpcm_db_inventory(ticket['hostname'])


#        if data:
#            # needs ticket.id which doesn't happen until after ticket created.
#            #self._attach_data_to_ticket(ticket, data)
#            pass
        


    def ticket_deleted(self, ticket):
        pass

    def ticket_comment_modified(self, ticket, cdate, author, comment, old_comment):
        pass

    def ticket_change_deleted(self, ticket, cdate, changes):
        pass



    def _hpcm_get_xname(self, hostname):
        
        try:
            aliases=self._hpcm_db_get_aliases()
            for node in aliases['nodes']:
                if node['name'] == hostname:
                    return node['aliases'].get('cm-geo-name', None)
        except Exception as e:
            self.log.error("HPCMDB, Error in _hpcm_get_xname: %s, %s",e,)

    def _hpcm_get_node(self, xname):
        try:
            aliases=self._hpcm_db_get_aliases()
            for node in aliases['nodes']:
                if node['aliases'].get('cm-geo-name') == xname:
                    return node['name']
        except Exception as e:
            self.log.error(f"HPCMDB, Error in _hpcm_get_node: {e}")
    
    def _hpcm_db_get_aliases(self):

        return(self._hpcm_db_get(aliasurl))
        
    def _hpcm_db_get(self, url):

        if os.path.exists(session_key_file):
            with open(session_key_file, 'r') as file:
                session_key = file.read().strip()
        else:
            sys.exit(1)
        headers = {'X-Auth-Token': session_key}
        response = requests.get(url, headers=headers, verify=False)


        if response.status_code == 403 or response.status_code == 401:  # Unauthorized access, indicating invalid session key
            self.log.debug("HPCMDB, Session key is invalid or expired.")
            sys.exit(1)

        if response.status_code == 200:
            try:
                data = response.json()
                return(data)
            except ValueError:
                self.log.debug("HPCMDB, Response is not valid JSON. Raw response:")
                self.log.debug(response.text)
                sys.exit(1)
        else:
            self.log.debug(f"HPCMDB, Failed with status code: {response.status_code}, Message: {response.text}")
            sys.exit(1)

    def _hpcm_db_inventory(self,hostname):
        inventoryurl=url_base+"nodes/"+hostname+"?fields=inventory"
        return(self._hpcm_db_get(inventoryurl))
    
    def _attach_data_to_ticket(self, ticket, data, filename='invnetory.json'):
        json_data = json.dumps(data, indent=4).encode('utf-8')

        json_file = io.BytesIO(json_data)
        json_file.seek(0, io.SEEK_END)  
        file_size = json_file.tell()     
        json_file.seek(0)


#    attachment = Attachment(self.env, 'ticket', ticket.id)

#    attachment.insert(filename, json_file, file_size)

