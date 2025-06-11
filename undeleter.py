#!/usr/bin/env python3
# -*- coding: utf8 -*-
### undeleter program for file management ###


# Copyright (C) 2025 Rajabov
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, version 3.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License along with this program. If not, see https://www.gnu.org/licenses/.

import re
import sys
import socket
import select
import time
import json
import pathlib
import ast
import pickle
import copy
import stat
import shutil
import fcntl
import struct
import subprocess
import shlex
import argparse
import random
import string
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer
from urllib.parse import unquote


HOST = '0.0.0.0'
PORT = 999 
AUDIT_LOG = "/var/log/samba/audit.log"
UNDELETER_LOG = "/var/log/samba/undeleter_recovered.log"
RECOVER_GROUPS = ["teachers"]
SHARE_PATH = "/srv/public"
LANGUAGE = "English"
RENAMEAT = "renameat"
UNLINKAT = "unlinkat"

#regex function   
def Read_log(query, file_name):
    #print("INPUT", query)
    maxIndex = 7 # 7 is targetname
    parced_lines = []
    unparced_lines = []
    with open(file_name, "r", encoding='utf-8') as file:
        for line in file:
            try:
                single_line = {}
                parts = line.split('|')
                #print("PARTS", parts)
                prefix = parts.pop(0)
                domain_and_user = re.sub('.+smbd_audit: (.+)', r'\1', prefix).partition('\\')
                time = prefix.split(' ')[0]
                #time = datetime.fromisoformat(time)
                single_line['time'] = time
                single_line['domain'] = domain_and_user[0]
                single_line['user'] = domain_and_user[2]
                single_line['client'] = parts[0]
                single_line['ip'] = parts[1]
                single_line['share'] = parts[2]
                single_line['operation'] = parts[3]
                single_line['status'] = parts[4]
                single_line["sourcename"] = parts[5].strip()
                if len(parts) >= maxIndex+1:
                    print('MALFORMED LINE:', line)
                    unparced_lines.append(single_line)
                elif len(parts) == maxIndex:
                    single_line["targetname"] = parts[maxIndex-1].strip()
    
                parced_lines.append(single_line)
                #print(single_line)
            except IndexError:
                continue
 
    found_lines = []
    look_for = "/" + query
    for i in parced_lines:
        if  i["sourcename"].strip().endswith(look_for):
            found_lines.append(i)
    #print("RESULT", f'"{found_lines}"')

    return found_lines
    
def find_by_timestamp(query, file_name):
    #print("INPUT", query)
    maxIndex = 7 # 7 is targetname
    recovery_line = {}
    with open(file_name, "r", encoding='utf-8') as file:
        for line in file:
            try:
                single_line = {}
                parts = line.split('|')
                #print("PARTS", parts)
                prefix = parts.pop(0)
                domain_and_user = re.sub('.+smbd_audit: (.+)', r'\1', prefix).partition('\\')
                time = prefix.split(' ')[0]
                #time = datetime.fromisoformat(time)
                single_line['time'] = time
                single_line['domain'] = domain_and_user[0]
                single_line['user'] = domain_and_user[2]
                single_line['client'] = parts[0]
                single_line['ip'] = parts[1]
                single_line['share'] = parts[2]
                single_line['operation'] = parts[3]
                single_line['status'] = parts[4]
                single_line["sourcename"] = parts[5].strip()
                if len(parts) >= maxIndex+1:
                    print('MALFORMED LINE:', line)
                elif len(parts) == maxIndex:
                    single_line["targetname"] = parts[maxIndex-1].strip()
    
                if time == query:
                    recovery_line = single_line
                    break # found
                #print(single_line)
            except IndexError:
                continue
 
    return recovery_line
    
    
def Recover(original_path_str):
    '''Try to recover(move) file from recycle directory'''
    message = {"info": _("Not recovered")}
    recycle_dir = ".recycle"
    original_path = pathlib.Path(original_path_str)
    found_path = pathlib.Path(original_path.parents[0], pathlib.Path(recycle_dir), original_path.name)
    is_success = Move(original_path, found_path)
    if is_success:
        message = {"info": _("Recovered"),
                   "found_path": str(found_path)}
    #else:
    #    print("Not found in recycle")
    return message
    

def Rename(original_path_str, found_path_str):
    '''Try to rename(move) accidentally missplaced file from another directory'''
    message = {"info": _("Not renamed")}
    original_path = pathlib.Path(original_path_str)
    found_path = pathlib.Path(found_path_str)
    is_success = Move(original_path, found_path)
    if is_success:
        message = {"info": _("Renamed"),
                   "found_path": str(found_path)}

    return message
    
    
def Move(original_path, found_path):
    '''Agnostic file/dir mover''' 
    is_success = False
    if found_path.exists():
        if original_path.parent:
            original_path.parent.mkdir(parents=True, exist_ok=True) #create nested directory tree 
        if not original_path.exists():
            #found_path.chmod(mode) # TODO nested files and directories
            found_path.rename(original_path)
            is_success = True
        
        Copy_perms(original_path)
        
    return is_success
       
       
def Copy_perms(recovered_path):
    reference_path = pathlib.Path(SHARE_PATH)
    shutil.copystat(reference_path, recovered_path)
    for path in recovered_path.rglob("*"):

        try:
            shutil.copystat(reference_path, path)

        except FileNotFoundError:
            print("Error: The source or destination directory does not exist.")
        except Exception as e:
            print(f"An error occurred: {e}")


def Find_dir(single_dict, is_allowed):
    split_path = None
    if single_dict.get("sourcename"):
        split_path = single_dict.get("sourcename").split("/")
        split_path = split_path[-1]

    return split_path
    

def Save_recovered(file_path, recovered_dict):
    '''Wright recovered entries to a file'''
    try:
        p = pathlib.Path(file_path)
        print(f'Opening {p}')
        with p.open("a", newline="\n", encoding="UTF-8") as f:
            dumps = json.dumps(recovered_dict)
            #print("DUMPS", dumps)
            f.write(dumps + "\n") #instead of string, for in keys and items, confirm string, key = value f'{key}={value}'
            
            result = True

    except PermissionError:
        result = False
        
    #print("APPENDED TEXT", p.read_text())
    
    return result


def Recall_recovered(file_path):
    '''Read previously recovered entries from a file'''
    p = pathlib.Path(file_path)
    result = []
    if p.is_file():
        try:
            text = p.read_text(encoding="UTF-8")
            lines = text.splitlines()
            for l in lines:
                converted = json.loads(l)
                result.append(converted)    
        except SyntaxError:
            raise
        except PermissionError:
            print("PermissionError: Unable to open", file_path)
        except:
            print("UNABLE TO LOAD JSON")
    else:
        print(f'{type(p)} is not a file')
    return result


def CrossValidate(found, already_recovered):
    for n, l in enumerate(copy.deepcopy(found)):
        time = l.get("time")
        if l in already_recovered:
            found[n]["recovered"] = True
            
    for i in found:
        print("I!!!!!", i)
    return found
 

def is_conn_allowed(addr, out):
    """Check if user is allowed to view smbstatus. More than one session is not allowed""" 
    is_success = False
    if addr and out:
        parced = json.loads(out)
        if parced.get("sessions"):
            all_users = set()
            is_auth = False
            for k,v in parced["sessions"].items():
                uid = v.get("uid")
                all_users.add(uid)
                gid = v.get("gid")
                remote_host_re = v.get("hostname")
                remote_host = re.sub('^ipv\d:(.+):\d+$', r'\1', remote_host_re)
                name = get_name_by_uid(uid)
                is_valid = is_valid_user(name, RECOVER_GROUPS)
                
                if is_valid and (addr == remote_host):
                    is_auth = True

            if is_auth and len(all_users) == 1:
                is_success = True
            elif is_auth and len(all_users) >= 2:
                print('LOGGED IN USERS:', len(all_users))
                is_success = True # DESTROY SECURITY TODO

    return is_success

  
def run_smbstatus():
    """Get output of smbstatus command"""
    message = {"info": None}
    out = None
    try:
        out_raw = subprocess.run(["smbstatus", "-j"], capture_output=True)
        out = out_raw.stdout
    except FileNotFoundError:
        message = {"info": _("smbstatus not found on server")}
    except Exception as e:
        print("EXCEPTION", e)
    
    return out


def is_valid_user(user, recover_groups):
    """Check if fullname user is a member of valid groups"""
    user_groups = get_user_groups_by_name(user)
    is_valid = False
    for i in recover_groups:
        if i in user_groups:
            is_valid = True
            break
    return is_valid
    

def get_sid_by_name(name):
    """ged SID from full username"""
    out = subprocess.run(["wbinfo", "-n", name], capture_output=True)
    sid = out.stdout
    sid = sid.split()
    if sid:
        sid = sid[0].decode("utf-8")
    else:
        sid = None
    return sid
    
    
def get_name_by_uid(uid):
    """get fullname from numeric UID"""
    uid = str(uid) #from int
    out = subprocess.run(["wbinfo", "-U", uid], capture_output=True)
    sid = out.stdout.strip()    
    name_out = subprocess.run(["wbinfo", "-s", sid], capture_output=True)
    name = name_out.stdout.split()
    if name:
        name = name[0].decode("utf-8")
    else:
        name = None
    return name
    

def get_user_groups_by_name(user):
    """find user groups as list by full user name"""
    regex = r"^.+\\"
    out = subprocess.run(["id", user], capture_output=True)
    unparced_id = out.stdout.decode('utf-8')
    groups_regex = re.search(r" groups=(.+[)])(:?\s|$)", unparced_id)
    groups = []
    if groups_regex:
        groups_id = groups_regex.group(1).split(",")
        for j in groups_id:
            g = re.search(".+\((.+)\)", j)
            if g:
                group = g.group(1).strip()
                group = re.sub(regex, "", group)
                groups.append(group)           
    return groups
    
    
def _(s):
    '''Translate incoming string'''
    russianStrings = {'Got connection from': 'Получено сообщение от',
                      'Server is listening on': 'Сервер слушает на',
                      'Not recovered': 'Не восстановлено',
                      'Recovered': 'Восстановлено',
                      'Not renamed': 'Не переименовано',
                      'Renamed': 'Переименовано',
                      'smbstatus not found on server': 'smbstatus не найден на сервере',
                     }
    deutschStrings = {'Got connection from': 'Verbindung hergestellt von',
                      'Server is listening on': 'der Server hört auf',
                      'Not recovered': 'Nicht wiederhergestellt',
                      'Recovered': 'Wiederhergestellt',
                      'Not renamed': 'Nicht umbenannt',
                      'Renamed': 'Umbenannt',
                      'smbstatus not found on server': 'smbstatus auf dem Server nicht gefunden',
                     }

    try:
        if LANGUAGE == 'English' or not LANGUAGE:
            return s
        elif LANGUAGE == 'Deutsch':
            return deutschStrings[s]
        elif LANGUAGE == 'Russian':
            return russianStrings[s]
        else:
            raise ValueError('Invalid language')
    except KeyError:
        print('NO TRANSLATION:', s)
        return f"NT: {s}"


class HttpGetHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        decoded_url = unquote(self.path)
        print(decoded_url)

        client_message = decoded_url.removeprefix('/search/')
        found_lines = Read_log(client_message, AUDIT_LOG)
        print('GET MSG:', client_message)
        #print(self.client_address)
        #print(self.path)
        if found_lines:
            json_data = json.dumps(found_lines)
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(bytes(json_data, 'utf8'))
        else:
            self.send_response(204)
            self.end_headers()

    def do_POST(self):
        self.send_header("Content-type", "application/json")
        content_length = int(self.headers['Content-Length'])

        post_data = json.loads(self.rfile.read(content_length).decode())
        print('POST MSG:', post_data)
        recover_line = find_by_timestamp(post_data.get('time'), AUDIT_LOG)
        status = do_recovery(recover_line)
        print('RECOVER_LINE:', recover_line)
        print('STATUS', status)
        try:
            json_data = json.dumps(status)
        except Exception:
            print('UNABLE TO LOAD JSON')
            json_data = {}

        if status.get("status").get("info"):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(bytes(json_data, "utf8"))
        else:
            self.send_response(204)
            self.end_headers()

        print('POST_DATA:', post_data)


def do_recovery(line):
    '''Move deleted or renamed files and folders to original destinations'''
    status = {"status": {"info": None}}
    err = {"info": None}
    reply = {"info": None}
    if line.get("operation") == RENAMEAT and not line.get("targetname"):
        print("NO TARGETNAME:", line)
    if line.get("operation") == RENAMEAT and line.get("status") == "ok":
        if not line.get("targetname"):
            reply = {"info": "targetname is not provided BY THE CLIENT"} #TODO move to child function
        else:
            reply = Rename(line.get("sourcename"), line.get("targetname"))
        status = {"status": reply}
    elif line.get("operation") == UNLINKAT and line.get("status") == "ok":
        recover_reply = Recover(line.get("sourcename"))
        if recover_reply:
            status = {"status": recover_reply}
    else:
        print("NO DICTIONARY MATCH")
    
    if status:
        Save_recovered(UNDELETER_LOG, line)

    return status


def handleArgs():

    parser = argparse.ArgumentParser()
    parser.add_argument('--unsecure', action='store_true',
                        default=False,
                        help='Skip MAC confinement check. Strongly discouraged')

    args = parser.parse_args()

    return args


def failIfNotConfined(profileBasename):
    '''Attempt to create unpredictably named file to determine if process is confined by any MAC.
       Only covers confinement, not necessarily enforcement'''
    randomTail = ''.join(random.choice(string.ascii_letters) for i in range(8))
    path = f'/dev/shm/{profileBasename}.am_i_confined.{randomTail}'

    try:
        with open(path, 'w') as f:
            f.write("DELETEME\n")
    except Exception:  # expected behavior
        pass

    f = pathlib.Path(path)
    if f.is_file():
        f.unlink()
        raise EnvironmentError(f'''The process is not confined by AppArmor. Refusing to function. Expected action:\n
$ sudo install -m 600 -o root -g root apparmor.d/{profileBasename} /etc/apparmor.d/
$ sudo apparmor_parser --add /etc/apparmor.d/{profileBasename}''')

    return None
                

def Listen(server_class=HTTPServer, handler_class=HttpGetHandler):
    '''Start listening as HTTP server'''
    server_address = ('', PORT)
    httpd = server_class(server_address, handler_class)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()


if __name__ == '__main__':

    args = handleArgs()
    if not args.unsecure:
        failIfNotConfined(pathlib.Path(sys.argv[0]).stem)
    
    Listen()
    
