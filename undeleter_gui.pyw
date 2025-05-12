# -*- coding: utf8 -*-

# Copyright (C) 2025 Rajabov
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, version 3.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License along with this program. If not, see https://www.gnu.org/licenses/.

import json
import tkinter as tk
#from datetime import datetime
from tkinter import ttk, messagebox, StringVar
from PIL import Image, ImageTk
import os
from copy import deepcopy
import urllib.request
from urllib.parse import quote 


SERVER = '192.168.76.128'
PORT = 999 #lower port for running as root
LOGO_PATH = "./image.png"
#RECOVERED_INDEXES = set() 
FOUND_LINES = [] #Stores result of last search
RENAMEAT = "renameat" #Realese specific system call for renaming (moving)
UNLINKAT = "unlinkat" #Realese specific system call for deleting
PATH_TO_SHARE = {"/srv/public": "P:",
                 "/storage/public": "P:",
                } # Map paths to share letters for convenience 


LANGUAGES = {
    "English": "English", 
    "Russian": "Русский",
    "German": "Deutsch"
}# See underscore _() function

LANGUAGE = "Russian" #Language by default


def search_call(client_query):
    '''Make GET HTTP call to server with URL as query'''
    try:
        encoded_query = quote(client_query, safe='', encoding='utf-8')
        url = f"http://{SERVER}:{PORT}/search/{encoded_query}"
        server_response_obj = urllib.request.urlopen(url)
        response_code = server_response_obj.getcode()
        print("\nCODE:", response_code)
        result = []
        if response_code == 200:
            server_response_data = server_response_obj.read()
            server_response_str = server_response_data.decode()
            print("SERVER RESPONSE:", server_response_str)
            result = json.loads(server_response_str)
        elif response_code == 204:
            result = [{'info': _('No matches found')}] 
    except urllib.error.URLError as e:
        print(f'UNABLE TO CONNECT (SEARCH)! Error: {e}')
        result = [{'info': _('Unable to connect (search)')}]
    except json.JSONDecodeError as e:
        print(f'JSON DECODE ERROR (SEARCH)! Error: {e}, Response: {server_response_str}')
        result = [{'info': _('Error decoding server response')}]
    except Exception as e:
        print(f'UNEXPECTED ERROR (SEARCH)! Error: {e}')
        result = [{'info': _('An unexpected error occurred during search')}]
    return result

def restore_call(restore_timestamp):
    '''Make POST HTTP call to server with timestamp as payload for recovery'''
    url = f"http://{SERVER}:{PORT}/recover/"
    req = urllib.request.Request(url, method='POST')
    req.add_header('Content-Type', 'application/json')

    data = {}
    data["time"] = restore_timestamp
    data_json = json.dumps(data)
    data_encoded = data_json.encode()
    
    server_answer = {}
    try:
        r = urllib.request.urlopen(req, data=data_encoded)
        response_content = r.read().decode() 
        print("Raw restore response:", response_content)
        try:
            server_answer = json.loads(response_content)
            print("SERVER ANSWER", server_answer)
        except json.JSONDecodeError:
            raise 
            print(f"Restore response was not JSON: {response_content}")
            info_text = _("Non-JSON response from server") # Utilising underscore _ function for translation
            if r.getcode() != 200: 
                info_text = f"{_('Server error code:')} {r.getcode()}"
            server_answer = {"status": {"info": info_text, "found_path": response_content}}
    except urllib.error.URLError as e:
        raise 
        print(f"Unable to connect for restore: {e}")
        server_answer = {"status": {"info": _("Unable to connect (restore)")}}
    #except Exception as e:
    #    print(f"Error during restore call: {e}")
    #    server_answer = {"status": {"info": str(e)}} 
        
    print("Parsed restore_call response:", server_answer)
    return server_answer
        
def search(search_name):
    global FOUND_LINES 
    if not search_name:
        messagebox.showwarning(_("Warning"), _("Please enter the search query!"))
        info_display_var.set("") 
        return

    info_display_var.set(f"{_('Searching for:')} {search_name}")
    if 'root' in globals() and root: root.update_idletasks()
    
    found_entries = search_call(search_name)
    FOUND_LINES = found_entries 
    
    create_treeview(found_entries)

    if found_entries is not None:
        button_restore.config(state=tk.NORMAL)
        info_display_var.set(f"{_('Search finished. Found entries:')} {len(found_entries)}")
    else:
        info_display_var.set(_("Search error"))
    root.update_idletasks()
    
    


def restore():
    global FOUND_LINES, tv, button_restore, info_display_var, root
    
    tv_focus_item = tv.focus() 
    if not tv_focus_item: 
        messagebox.showwarning(_("Error"), _("Select the row for recovery"))
        info_display_var.set("") 
        return
        
    tv_focus_values = tv.item(tv_focus_item).get("values")
    print("FOCUS VALUES", tv_focus_values)

    if not tv_focus_values: 
        messagebox.showwarning(_("Error"), _("Selected row has no data."))
        info_display_var.set("")
        return
    
    original_time_value = None
    try:
        time_column_header = _("time")
        column_headers = list(tv["columns"]) # Убедимся, что это список
        time_column_index = -1
        if time_column_header in column_headers:
            time_column_index = column_headers.index(time_column_header)
        
        if time_column_index != -1:
            original_time_value = tv_focus_values[time_column_index]
            print(f"Extracted time for restore: {original_time_value} from column index {time_column_index}")
        else:
            messagebox.showerror(_("Error"), _("Could not find time column for restoration."))
            return
            
    except Exception as e:
        print(f"Error finding time value for restore: {e}")
        messagebox.showerror(_("Error"), _("Error processing selected row for restoration."))
        return

    if not original_time_value: 
        messagebox.showerror(_("Error"), _("Could not determine timestamp for restoration."))
        return

    to_restore_timestamp = original_time_value
    current_tags = tv.item(tv_focus_item, "tags")

    if "recovered" in current_tags:
        msg_box = messagebox.askquestion(
            _("Already recovered"), _("This item is marked as recovered. Try to recover again?"), icon="question"
        )
        if msg_box != "yes":
            info_display_var.set(_("Recovery canceled"))
            return 

    button_restore.config(state=tk.DISABLED) 
    info_display_var.set(f"{_('Attempting to restore item from time:')} {to_restore_timestamp}")
    root.update_idletasks()

    server_answer = restore_call(to_restore_timestamp) 
    print(_("Recovery result:"), server_answer)

    status_info = _("Error") 
    found_path_display = ""

    if isinstance(server_answer, dict) and "status" in server_answer and isinstance(server_answer["status"], dict):
        status_info = server_answer["status"].get("info", _("Unknown status"))
        found_path = server_answer["status"].get("found_path")

        if found_path: 
            found_path_display = str(found_path)

        if status_info == "recovered":
            info_display_var.set(f"{_('Successfully recovered:')} {found_path_display}")
            tv.item(tv_focus_item, tags=("recovered",)) 
            tv.tag_configure("recovered", background="light grey")
            
            if FOUND_LINES:
                for item_in_found_lines in FOUND_LINES:
                    if isinstance(item_in_found_lines, dict) and item_in_found_lines.get('time') == to_restore_timestamp:
                        item_in_found_lines['recovered'] = True 
                        break
        elif status_info == "already_recovered": 
            info_display_var.set(f"{_('Item was already recovered:')} {found_path_display}")
            tv.item(tv_focus_item, tags=("recovered",)) 
            tv.tag_configure("recovered", background="light grey")
        else: 
            info_display_var.set(f"{_('Recovery failed or status:')} {status_info}. {_('Details:')} {found_path_display}")
    else:
        info_display_var.set(_("Unknown error or invalid response from server during recovery."))

    root.update_idletasks()


def create_treeview(data_list):
    global tv, info_display_var

    for to_clean_row in tv.get_children():
        tv.delete(to_clean_row)
        
    if data_list is None or not isinstance(data_list, list):
        if info_display_var: info_display_var.set(_("Unable to load table data or data is invalid"))
        tv["columns"] = [] 
        return
        
    default_keys_order = ['sourcename', 'targetname', 'operation', 'client', 'time']
    display_columns_translated = [_ (key) for key in default_keys_order] # Заголовки столбцов (переведенные)

    if not data_list: 
        tv["columns"] = display_columns_translated
        tv.column("#0", width=0, stretch=tk.NO) 
        for key_orig, col_display_text in zip(default_keys_order, display_columns_translated):
            width = 250 if key_orig in ['sourcename', 'targetname'] else (180 if key_orig == 'time' else 120)
            tv.column(col_display_text, width=width, minwidth=80, anchor="w", stretch=tk.YES) 
            tv.heading(col_display_text, text=col_display_text, anchor='w')
        return

    data_list_processed = []
    for item_orig in deepcopy(data_list): 
        if not isinstance(item_orig, dict): 
            print(f"Skipping non-dict item in data_list: {item_orig}")
            continue
        if 'info' in item_orig: 
            print(f"Skipping info item in data_list: {item_orig}")
            continue

        i = item_orig.copy()

        for k_share, v_share in PATH_TO_SHARE.items():
            if i.get("sourcename", "").startswith(k_share):
                i["sourcename"] = v_share + i["sourcename"].removeprefix(k_share)
            if i.get("targetname") and i.get("targetname", "").startswith(k_share): 
                i["targetname"] = v_share + i["targetname"].removeprefix(k_share)
        
        if i.get("operation") == UNLINKAT:
            i["operation_display"] = _("deleted") 
        elif i.get("operation") == RENAMEAT:
            i["operation_display"] = _("moved")
        else:
            i["operation_display"] = i.get("operation", "") 

        data_list_processed.append(i)

    if not data_list_processed: 
        tv["columns"] = display_columns_translated
        tv.column("#0", width=0, stretch=tk.NO)
        for key_orig, col_display_text in zip(default_keys_order, display_columns_translated):
            width = 250 if key_orig in ['sourcename', 'targetname'] else (180 if key_orig == 'time' else 120)
            tv.column(col_display_text, width=width, minwidth=80, anchor="w", stretch=tk.YES)
            tv.heading(col_display_text, text=col_display_text, anchor='w')
        return

    # Ключи для извлечения данных из item_data в правильном порядке для отображения
    # `operation_display` содержит уже переведенное значение операции
    keys_for_data_extraction = ['sourcename', 'targetname', 'operation_display', 'client', 'time']

    tv["columns"] = display_columns_translated
    tv.column("#0", width=0, stretch=tk.NO) 
    for key_orig, header_text in zip(default_keys_order, display_columns_translated): # Используем default_keys_order для определения ширины
        width = 250 if key_orig in ['sourcename', 'targetname'] else (180 if key_orig == 'time' else 120)
        tv.column(header_text, width=width, minwidth=80, anchor="w", stretch=tk.YES)
        tv.heading(header_text, text=header_text, anchor='w')
    
    # Сортировка данных: сначала самые новые (по времени)
    # Предполагаем, что поле 'time' содержит ISO-совместимую строку времени
    try:
        data_list_processed.sort(key=lambda x: x.get('time', ''), reverse=True)
    except Exception as e:
        print(f"Could not sort data by time: {e}")


    for item_data in data_list_processed: 
        row_values = []
        for key in keys_for_data_extraction: # Извлекаем значения по ключам
            row_values.append(item_data.get(key, '')) 
        
        item_tags = []
        if item_data.get('recovered'): 
            item_tags.append("recovered")
            
        tv.insert('', 'end', values=row_values, tags=tuple(item_tags))
        
    tv.tag_configure("recovered", background="light grey")

# --- Функция перевода строк ---
def _(s):
    global LANGUAGE # Убедимся, что используем глобальную переменную

    english_strings = {
        "Undeleter client": "Undeleter client",
        "Please enter the search query!": "Please enter the search query!",
        "Searching for:": "Searching for:",
        "Search finished. Found entries:": "Search finished. Found entries:",
        "Search error": "Search error",
        "Error": "Error",
        "Warning": "Warning", 
        "Select the row for recovery": "Select the row for recovery",
        "Already recovered": "Already recovered",
        "Try to recover again?": "Try to recover again?",
        "This item is marked as recovered. Try to recover again?": "This item is marked as recovered. Try to recover again?",
        "Recovery canceled": "Recovery canceled.",
        "Recovery result:": "Recovery result:",
        "Successfully recovered:": "Successfully recovered:",
        "Item was already recovered:": "Item was already recovered:",
        "Recovery failed or status:": "Recovery failed or status:",
        "Details:": "Details:",
        "Unknown error:": "Unknown error:",
        "Unable to load table data": "Unable to load table data",
        "Unable to load table data or data is invalid": "Unable to load table data or data is invalid",
        "Search": "Search",
        "Recover": "Recover",
        "Exit": "Exit",
        "Ready to work": "Ready to work",
        "Exact file/folder name:": "Exact file/folder name:",
        "File not found:": "File not found:", 
        "Error loading the image:": "Error loading the image:",
        "moved": "moved", # значение для операции
        "deleted": "deleted", # значение для операции
        "time": "Time", 
        "client": "Client", 
        "operation": "Operation", 
        "sourcename": "Source Path", 
        "targetname": "Target Path", 
        "No matches found": "No matches found", 
        "Unable to connect (search)": "Unable to connect (search)",
        "Error decoding server response": "Error decoding server response",
        "An unexpected error occurred during search": "An unexpected error occurred during search",
        "Unable to connect (restore)": "Unable to connect (restore)",
        "Selected row has no data.": "Selected row has no data.",
        "Could not find time column for restoration.": "Could not find time column for restoration.",
        "Error processing selected row for restoration.": "Error processing selected row for restoration.",
        "Could not determine timestamp for restoration.": "Could not determine timestamp for restoration.",
        "Attempting to restore item from time:": "Attempting to restore item from time:",
        "Unknown status": "Unknown status",
        "Unknown error or invalid response from server during recovery.": "Unknown error or invalid response from server during recovery.",
        "Search error or no results": "Search error or no results",
        "Non-JSON response from server": "Non-JSON response from server",
        "Server error code:": "Server error code:",
    }

    russianStrings = {
        "Undeleter client": "Клиент Undeleter",
        "Please enter the search query!": "Пожалуйста, введите запрос для поиска!",
        "Searching for:": "Идет поиск по запросу:",
        "Search finished. Found entries:": "Поиск завершен. Найдено записей:",
        "Search error": "Ошибка поиска",
        "Error": "Ошибка",
        "Warning": "Предупреждение",
        "Select the row for recovery": "Выберите строку для восстановления!",
        "Already recovered": "Уже восстановлено",
        "Try to recover again?": "Попытаться восстановить еще раз?",
        "This item is marked as recovered. Try to recover again?": "Этот элемент уже помечен как восстановленный. Попробовать восстановить снова?",
        "Recovery canceled": "Восстановление отменено.",
        "Recovery result:": "Результат восстановления:",
        "Successfully recovered:": "Успешно восстановлено:",
        "Item was already recovered:": "Элемент уже был восстановлен:",
        "Recovery failed or status:": "Ошибка восстановления или статус:",
        "Details:": "Подробности:",
        "Unknown error:": "Неизвестная ошибка:",
        "Unable to load table data": "Не удалось загрузить данные для таблицы.",
        "Unable to load table data or data is invalid": "Не удалось загрузить данные для таблицы или данные неверны.",
        "Search": "Поиск",
        "Recover": "Восстановить",
        "Exit": "Выход",
        "Ready to work": "Готово к работе",
        "Exact file/folder name:": "Точное название файла/папки:",
        "File not found:": "Файл не найден:",
        "Error loading the image:": "Ошибка загрузки изображения:",
        "moved": "перемещен", 
        "deleted": "удален",   
        "time": "Время",
        "client": "Клиент",
        "operation": "Операция",
        "sourcename": "Исходный путь",
        "targetname": "Новый путь", 
        "No matches found": "Совпадений не найдено",
        "Unable to connect (search)": "Не удалось подключиться (поиск)",
        "Error decoding server response": "Ошибка декодирования ответа сервера",
        "An unexpected error occurred during search": "Произошла непредвиденная ошибка во время поиска",
        "Unable to connect (restore)": "Не удалось подключиться (восстановление)",
        "Selected row has no data.": "Выбранная строка не содержит данных.",
        "Could not find time column for restoration.": "Не удалось найти столбец времени для восстановления.",
        "Error processing selected row for restoration.": "Ошибка обработки выбранной строки для восстановления.",
        "Could not determine timestamp for restoration.": "Не удалось определить временную метку для восстановления.",
        "Attempting to restore item from time:": "Попытка восстановления элемента по времени:",
        "Unknown status": "Неизвестный статус",
        "Unknown error or invalid response from server during recovery.": "Неизвестная ошибка или неверный ответ от сервера при восстановлении.",
        "Search error or no results": "Ошибка поиска или нет результатов",
        "Non-JSON response from server": "Ответ сервера не в формате JSON",
        "Server error code:": "Код ошибки сервера:",
    }
    deutschStrings = {
        "Undeleter client": "Undeleter Klient", 
        "Please enter the search query!": "Bitte geben Sie den Suchbegriff ein!", 
        "Searching for:": "Suche nach:",
        "Search finished. Found entries:": "Suche abgeschlossen. Gefundene Einträge:",  
        "Search error": "Fehler bei der Suche",
        "Error": "Fehler",
        "Warning": "Warnung",
        "Select the row for recovery": "Wählen Sie die Zeile zur Wiederherstellung aus!", 
        "Already recovered": "Bereits wiederhergestellt",
        "Try to recover again?": "Erneut versuchen, wiederherzustellen?",
        "This item is marked as recovered. Try to recover again?": "Dieses Element ist als wiederhergestellt markiert. Erneut versuchen?",
        "Recovery canceled": "Wiederherstellung abgebrochen.", 
        "Recovery result:": "Wiederherstellungsergebnis:",
        "Successfully recovered:": "Erfolgreich wiederhergestellt:",
        "Item was already recovered:": "Element wurde bereits wiederhergestellt:",
        "Recovery failed or status:": "Wiederherstellung fehlgeschlagen oder Status:",
        "Details:": "Details:",
        "Unknown error:": "Unbekannter Fehler:",
        "Unable to load table data": "Tabellendaten konnten nicht geladen werden.", 
        "Unable to load table data or data is invalid": "Tabellendaten konnten nicht geladen werden oder Daten sind ungültig.",
        "Search": "Suchen",
        "Recover": "Wiederherstellen",
        "Exit": "Beenden", 
        "Ready to work": "Bereit", 
        "Exact file/folder name:": "Genauer Datei-/Ordnername:", 
        "File not found:": "Datei nicht gefunden:",
        "Error loading the image:": "Fehler beim Laden des Bildes:",
        "moved": "verschoben", 
        "deleted": "gelöscht",  
        "time": "Zeit",
        "client": "Client", 
        "operation": "Aktion", 
        "sourcename": "Quellpfad", 
        "targetname": "Zielpfad",    
        "No matches found": "Keine Übereinstimmungen gefunden",
        "Unable to connect (search)": "Verbindung fehlgeschlagen (Suche)",
        "Error decoding server response": "Fehler beim Dekodieren der Serverantwort",
        "An unexpected error occurred during search": "Ein unerwarteter Fehler ist während der Suche aufgetreten",
        "Unable to connect (restore)": "Verbindung fehlgeschlagen (Wiederherstellung)",
        "Selected row has no data.": "Ausgewählte Zeile enthält keine Daten.",
        "Could not find time column for restoration.": "Zeitspalte für die Wiederherstellung nicht gefunden.",
        "Error processing selected row for restoration.": "Fehler beim Verarbeiten der ausgewählten Zeile für die Wiederherstellung.",
        "Could not determine timestamp for restoration.": "Zeitstempel für die Wiederherstellung konnte nicht ermittelt werden.",
        "Attempting to restore item from time:": "Versuche Element wiederherzustellen von Zeit:",
        "Unknown status": "Unbekannter Status",
        "Unknown error or invalid response from server during recovery.": "Unbekannter Fehler oder ungültige Antwort vom Server während der Wiederherstellung.",
        "Search error or no results": "Suchfehler oder keine Ergebnisse",
        "Non-JSON response from server": "Antwort des Servers nicht im JSON-Format",
        "Server error code:": "Server-Fehlercode:",
    }
    
    active_translation_map = english_strings 

    if LANGUAGE == 'English':
        active_translation_map = english_strings
    elif LANGUAGE == 'Russian':
        active_translation_map = russianStrings
    elif LANGUAGE == 'German': 
        active_translation_map = deutschStrings
    
    translated = active_translation_map.get(s)
    if translated is not None:
        return translated
    else:
        fallback_translated = english_strings.get(s)
        if fallback_translated is not None:
            print(f"Translation missing for '{s}' in {LANGUAGE}, using English fallback.")
            return fallback_translated
        else:
            print(f"Untracked string for translation: '{s}' (Language: {LANGUAGE})")
            return f"NT: {s}"


def change_language(event=None):
    '''Change language via combobox'''
    global LANGUAGE, FOUND_LINES, lang_var, root, label_exact_name, button_search, button_restore, info_display_var, tv, lang_combobox

    selected_language_key = lang_var.get() 

    if selected_language_key not in LANGUAGES.keys():
        print(f"Warning: Selected language '{selected_language_key}' not recognized. Reverting to {LANGUAGE}.")
        if lang_combobox: lang_combobox.set(LANGUAGE) 
        return

    LANGUAGE = selected_language_key 

    root.title(_("Undeleter client"))
   
    label_exact_name.config(text=_("Exact file/folder name:"))
    button_search.config(text=_("Search"))
    button_restore.config(text=_("Recover"))
    info_display_var.set(_("Ready to work"))
    
    create_treeview(FOUND_LINES)

if __name__ == '__main__':
    root = tk.Tk()
    
    root.geometry('1100x650') 
    root.configure(background="#00008B")

    frame_top = tk.Frame(root, background="#00008B")
    frame_top.pack(fill=tk.X, padx=10, pady=5)

    # Select language
    lang_var = StringVar(root)
    language_options = list(LANGUAGES.keys()) 
    lang_combobox = ttk.Combobox(frame_top, textvariable=lang_var, 
                                 values=language_options, state="readonly", width=12) 
    
    if LANGUAGE in language_options:
        lang_combobox.set(LANGUAGE)
    else: 
        lang_combobox.set(language_options[0] if language_options else "")

    lang_combobox.pack(side=tk.RIGHT, padx=(0,10), pady=5) 
    lang_combobox.bind("<<ComboboxSelected>>", change_language)
    # End of selecting language

    # Load logo image
    logo_label_widget = None
    if os.path.exists(LOGO_PATH):
        try:
            img = Image.open(LOGO_PATH)
            img = img.resize((80, 80), Image.Resampling.LANCZOS)
            bb_img = ImageTk.PhotoImage(img)

            logo_label_widget = tk.Label(frame_top, image=bb_img, background="#00008B")
            logo_label_widget.image = bb_img 
            logo_label_widget.pack(side=tk.LEFT, padx=(0, 10)) 
        except Exception as e:
            print(_("Error loading the image:"), e) 
    else:
        print(_("File not found:"), LOGO_PATH) 

    label_exact_name = ttk.Label(frame_top, text=_("Exact file/folder name:"), foreground="white", background="#00008B")
    label_exact_name.pack(side=tk.LEFT, padx=5)

    # Input text for search
    inputtxt = ttk.Entry(frame_top, width=50, state="normal")
    inputtxt.focus_set()
    inputtxt.pack(side=tk.LEFT, padx=5)

    # Group of buttons
    button_search = ttk.Button(frame_top, text=_("Search"), command= lambda: search(inputtxt.get().strip()))
    root.bind("<Return>", (lambda e_return: search(inputtxt.get().strip())))
    button_search.pack(side=tk.LEFT, padx=5)

    button_restore = ttk.Button(frame_top, text=_("Recover"), command=restore) 
    button_restore.pack(side=tk.LEFT, padx=5)
    button_restore.config(state=tk.DISABLED) 

    # Search results
    tree_frame = tk.Frame(root)
    tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    tv = ttk.Treeview(tree_frame, show='headings', height=12)
    tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tv.yview)
    tv.configure(yscrollcommand=tree_scroll.set)
    tree_scroll.pack(side="right", fill="y")
    tv.pack(side="left", fill=tk.BOTH, expand=True)
    
    try: 
        root.state('zoomed')
    except tk.TclError:
        print("Could not zoom the window. Using default size.")

    info_display_var = StringVar(root)
    
    # Determine dynamic wraplength
    root.update_idletasks() # update to aquire current geometry
    wraplength_val = root.winfo_width() - 40 if root.winfo_width() > 40 else 300

    info_display_label = ttk.Label(
        root,
        textvariable=info_display_var,
        wraplength=wraplength_val, 
        anchor='w',
        justify='left',
    )
    info_display_label.pack(padx=10, pady=(5, 10), fill=tk.X, side=tk.BOTTOM)

    root.title(_("Undeleter client")) 
    label_exact_name.config(text=_("Exact file/folder name:")) 
    button_search.config(text=_("Search"))
    button_restore.config(text=_("Recover"))
    info_display_var.set(_("Ready to work"))
    
    create_treeview([]) 

    root.mainloop()