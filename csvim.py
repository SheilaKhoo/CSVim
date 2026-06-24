import curses
import traceback
import argparse
import signal
import re

parser = argparse.ArgumentParser()
parser.add_argument('--file', dest='filename', type=str, help='Specify .csv file here')
args = parser.parse_args()
filename = args.filename

import pandas as pd
import sys
import uuid

# Enter: 10
# Backspace: 127
# q: 113 / Q: 81 / Esc: 27
# Up: 279165 / Down: 279166 / Left: 279168 / Right: 279167
# Del: 279151126
# a: 97 | z: 122
# A: 65 | Z: 90
# , 44 | . 46
# < 60 | > 62
# / 47 | ? 63
# : 58 | ; 59
# " 34 | ' 39
# [ 91 | ] 93
# { 123 | } 125
# | 124 | \ 92
# ` 96 | ~ 126
# 0 48 | 9 57
# ! 33 | @ 64 | # 35 | $ 36 | % 37 | ^ 94 | & 38 | * 42 | ( 40 | ) 41
# - 45 | _ 95
# + 43 | = 61
valid_chars = [32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 58, 59, 60, 61, 62, 63, 64, 91, 92, 93, 94, 95, 96, 123, 124, 125, 126]
for i in range(97, 123): # Add a-z
    valid_chars.append(i)
for i in range(65, 91): # Add A-Z
    valid_chars.append(i)
for i in range(48, 58): # Add 0-9
    valid_chars.append(i)
RESERVED_ROWS = 2
RESERVED_ROWS_BOT = 1
posX = 0
posY = 0
cell_row_selection = 0
cell_col_selection = 0
cell_editor_char_pos = None
cell_editor_start_pos = -1
menu_selection = True

def debug_test(data):
    screen.addstr(14, 14, str(data), curses.A_UNDERLINE)
    screen.refresh()
    curses.napms(500)

# Handle Ctrl+C
def signal_handler(sig, frame):
    pass
signal.signal(signal.SIGINT, signal_handler)

def end_program():
    curses.curs_set(1)
    curses.nocbreak()
    curses.echo()
    screen.keypad(False)
    curses.endwin()

def print_df(df, start_row, start_col, selected_row=None, selected_col=None, mode="Main"):
    # Default to first cell selected if None
    if selected_row == None:
        selected_row = start_row
    if selected_col == None:
        selected_col = start_col
    # Determine end row
    end_row = start_row + num_rows - RESERVED_ROWS - RESERVED_ROWS_BOT# Reserve 2 rows for text editor and header
    if end_row > len(df):
        end_row = len(df)
    # Initialize x position
    print_x = 0
    # Loop through each column and print
    for current_col in range(start_col, len(list(df.columns))):
        print_row = RESERVED_ROWS # Reserve 2 rows for text editor and header
        # Print header
        col_header = str(list(df.columns)[current_col])
        if len(col_header) > num_cols - print_x - 1:
            col_header = col_header[:num_cols - print_x]
        try:
            if selected_row == -1 and selected_col == current_col:
                if col_header == "":
                    screen.addstr(1, print_x, " "*get_longest_length_of_col(df, current_col, print_x), curses.color_pair(6))
                else:
                    screen.addstr(1, print_x, (col_header + " "*(get_longest_length_of_col(df, current_col, print_x)-len(col_header)))[:num_cols - print_x], curses.color_pair(6) | curses.A_UNDERLINE | curses.A_BOLD)
            else:
                screen.addstr(1, print_x, col_header, curses.A_UNDERLINE)
        except curses.error:
            pass # Trapping error as curses has some weird bug which errors when you print on last column
        # Print cell data
        for i in df.iloc[start_row: end_row].index:
            cell_data = str(df.iloc[i, current_col]).replace('\n', '\\n')
            if len(cell_data) > num_cols - print_x - 1:
                cell_data = cell_data[:num_cols - print_x]
            # Check if i and current_col are selected cell
            if i == selected_row and current_col == selected_col:
                # Handle blank cells so they at least display something
                if mode == "Main" or mode == "Save" or mode == "Delete Row" or mode == "Delete Column":
                    STYLE = curses.color_pair(1)
                elif mode == "Cell":
                    STYLE = curses.A_BOLD
                if cell_data == "":
                    try:
                        screen.addstr(print_row, print_x, " "*get_longest_length_of_col(df, current_col, print_x), STYLE)
                    except curses.error:
                        pass
                else:
                    try:
                        screen.addstr(print_row, print_x, (cell_data + " "*(get_longest_length_of_col(df, current_col, print_x)-len(cell_data)))[:num_cols - print_x], STYLE)
                    except curses.error:
                        pass
            elif i == selected_row and mode == "Delete Row":
                try:
                    screen.addstr(print_row, print_x, (cell_data + " "*(get_longest_length_of_col(df, current_col, print_x)-len(cell_data)))[:num_cols - print_x], curses.color_pair(1))
                except curses.error:
                    pass
            elif current_col == selected_col and mode == "Delete Column":
                try:
                    screen.addstr(print_row, print_x, (cell_data + " "*(get_longest_length_of_col(df, current_col, print_x)-len(cell_data)))[:num_cols - print_x], curses.color_pair(1))
                except curses.error:
                    pass
            else:
                try:
                    screen.addstr(print_row, print_x, cell_data)
                except curses.error:
                    pass # Trapping error as curses has some weird bug which errors when you print on last column
            print_row += 1
        # Get longest length of this column
        longest_length = get_longest_length_of_col(df, current_col, print_x)
        print_x += longest_length + 1 # Add on to print_x position for next column
        if print_x > num_cols:
            break
    if mode == "Main":
        # Calculate A B C D E F for the cell col, like Excel
        cell_alphabet = convert_colnum(cell_col_selection)
        try:
            screen.addstr(num_rows - 1, 0, "[" + cell_alphabet + str(cell_row_selection+1) + "] Up/Down/Left/Right/W/A/S/D: Select Cell | Enter: Edit Cell | Shift+W/A/S/D: Add Row/Column | Del: Delete Row/Col | <: Undo | >: Redo | Q: Quit", curses.color_pair(5))
        except curses.error:
            pass
    elif mode == "Save" or mode == "Delete Row" or mode == "Delete Column":
        screen.addstr(num_rows - 1, 0, "Left/Right/A/D: Select Button | Enter: Confirm | Esc/Backspace: Back", curses.color_pair(5))

def convert_colnum(cell_alphabet_counter_input):
    cell_alphabet_counter = cell_alphabet_counter_input
    cell_alphabet = ""
    number_of_powered_deductibles = 1
    while number_of_powered_deductibles >= 0:
        # Get largest power deductible
        largest_power = 1
        while 26**(largest_power+1) <= cell_alphabet_counter:
            largest_power += 1
        # Check how many 26**X can be deducted from cell_alphabet_counter
        remainder = cell_alphabet_counter % 26**largest_power
        number_of_powered_deductibles = int((cell_alphabet_counter - remainder) / 26**largest_power) - 1
        if number_of_powered_deductibles < 0:
            cell_alphabet += chr(remainder + 65)
        else:
            cell_alphabet += chr(number_of_powered_deductibles + 65)
        # Deduct powered number
        cell_alphabet_counter = remainder
    return cell_alphabet

def get_longest_length_of_col(df, col, print_x):
    longest_length = 0
    for i in df.index:
        cell_data = str(df.iloc[i, col])
        if len(cell_data) > (num_cols - print_x):
            cell_data = cell_data[:num_cols - print_x]
        if len(cell_data) > longest_length:
            longest_length = len(cell_data)
    if len(list(df.columns)[col]) > longest_length:
        longest_length = len(list(df.columns)[col])
    return longest_length

def key_up():
    global cell_row_selection
    global posY
    # Handle cell selection
    if cell_row_selection > -1:
        cell_row_selection -= 1
    # Handle row panning
    if posY > 0 and (cell_row_selection < posY):
        posY -= 1
def key_down():
    global cell_row_selection
    global posY
    # Handle cell selection
    if cell_row_selection < len(df) - 1:
        cell_row_selection += 1
    # Handle row panning
    if (posY < len(df) - 1) and (cell_row_selection > (posY + num_rows - RESERVED_ROWS - 1 - RESERVED_ROWS_BOT)):
        posY += 1
def key_left():
    global cell_col_selection
    global posX
    # Handle cell selection
    if cell_col_selection > 0:
        cell_col_selection -= 1
    # Get last index of last full column
    start_index_of_prev_selection = -200000
    while ((posX > 0) and (start_index_of_prev_selection <= 0) and (posX != cell_col_selection)):
        total_length = 0
        start_index_of_prev_selection = 0
        for current_col in range(posX, len(list(df.columns))):
            longest_length = 0
            for i in df.index:
                cell_data = str(df.iloc[i, current_col])
                if len(cell_data) > (num_cols - total_length):
                    cell_data = cell_data[:num_cols - total_length]
                if len(cell_data) > longest_length:
                    longest_length = len(cell_data)
            if len(list(df.columns)[current_col]) > longest_length:
                longest_length = len(list(df.columns)[current_col])
            # If next selection will not go out of screen, we don't need to pan
            if current_col < cell_col_selection:
                start_index_of_prev_selection += longest_length + 1
            elif current_col == cell_col_selection:
                start_index_of_prev_selection += 1
            # Check total length of printed characters is more than screen length, stop appending, else append
            if total_length > num_cols:
                break
            else:
                total_length += longest_length + 1 # Add on to posX position for next column
        if (posX > 0) and (start_index_of_prev_selection <= 0) and (posX != cell_col_selection):
            posX -= 1
def key_right():
    global cell_col_selection
    global posX
    # Handle cell selection
    if cell_col_selection < len(list(df.columns)) - 1:
        cell_col_selection += 1
    # Get last index of last full column
    end_index_of_next_selection = -1
    while ((posX < len(list(df.columns)) - 1) and (end_index_of_next_selection >= num_cols) and (posX != cell_col_selection)) or end_index_of_next_selection == -1:
        total_length = 0
        end_index_of_next_selection = 0
        for current_col in range(posX, len(list(df.columns))):
            longest_length = 0
            longest_length_untruncated = 0
            for i in df.index:
                cell_data = str(df.iloc[i, current_col])
                if len(cell_data) > (num_cols - total_length):
                    cell_data = cell_data[:num_cols - total_length]
                if len(cell_data) > longest_length:
                    longest_length = len(cell_data)
                    longest_length_untruncated = len(str(df.iloc[i, current_col]))
            if len(list(df.columns)[current_col]) > longest_length:
                longest_length = len(list(df.columns)[current_col])
            if len(list(df.columns)[current_col]) > longest_length_untruncated:
                longest_length_untruncated = len(list(df.columns)[current_col])
            # If next selection will not go out of screen, we don't need to pan
            if current_col < cell_col_selection:
                end_index_of_next_selection += longest_length + 1
            elif current_col == cell_col_selection:
                end_index_of_next_selection += longest_length_untruncated
            # Check total length of printed characters is more than screen length, stop appending, else append
            if total_length > num_cols:
                break
            else:
                total_length += longest_length + 1 # Add on to posX position for next column
        if (posX < len(list(df.columns)) - 1) and (end_index_of_next_selection >= num_cols) and (posX != cell_col_selection):
            posX += 1

df_cache = []
df_cache_pos = -1
def cache_df():
    global df_cache
    global df
    global df_cache_pos
    MAX_CACHE = 10
    if df_cache_pos == -1:
        df_cache = df_cache + [df.copy(deep=True)]
        df_cache_pos = 0
        return
    if len(df_cache) < MAX_CACHE:
        if df_cache[df_cache_pos].equals(df.copy(deep=True)) == False:
            df_cache = df_cache[:df_cache_pos + 1] + [df.copy(deep=True)]
    else:
        if df_cache[df_cache_pos].equals(df.copy(deep=True)) == False:
            df_cache = df_cache[1:MAX_CACHE] + [df.copy(deep=True)]
    df_cache_pos = len(df_cache) - 1
def undo_df():
    global df_cache
    global df
    global df_cache_pos
    global cell_col_selection
    global cell_row_selection
    if df_cache_pos > 0:
        df_cache_pos -= 1
        df = df_cache[df_cache_pos].copy(deep=True)
        if cell_col_selection > len(df.columns) - 1:
            cell_col_selection = len(df.columns) - 1
        if cell_row_selection > len(df) - 1:
            cell_row_selection = len(df) - 1
def redo_df():
    global df_cache
    global df
    global df_cache_pos
    global cell_col_selection
    global cell_row_selection
    if df_cache_pos < len(df_cache) - 1:
        df_cache_pos += 1
        df = df_cache[df_cache_pos].copy(deep=True)
        if cell_col_selection > len(df.columns) - 1:
            cell_col_selection = len(df.columns) - 1
        if cell_row_selection > len(df) - 1:
            cell_row_selection = len(df) - 1

try:
    screen = curses.initscr()
    num_rows, num_cols = screen.getmaxyx()
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_WHITE) # Red text, white background
    curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK) # Cyan text, black background
    curses.init_pair(3, curses.COLOR_MAGENTA, curses.COLOR_BLACK) # For quit menu border
    curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK) # For quit menu title
    curses.init_pair(5, curses.COLOR_YELLOW, curses.COLOR_BLACK) # For bottom hints
    curses.init_pair(6, curses.COLOR_WHITE, curses.COLOR_RED) # Header selection
    curses.curs_set(0) # Disable cursor
    screen.keypad(True)
    #screen.addstr(0, 0, "Print at 0 0", curses.A_BOLD)
    #screen.addstr(3, 1, "Print at 3 1", curses.A_STANDOUT)
    #screen.addstr(4, 4, "Print at 4 4", curses.A_UNDERLINE)
    #screen.addstr(5, 0, "Print at 5 0", curses.color_pair(1) | curses.A_BLINK)
    #screen.refresh()
    #key = screen.getch()
    #screen.clear()

    #screen.addstr(10, 10, str(key))
    #screen.refresh()
    #curses.napms(5000)
    strname = ""
    mode = "Main"
    if filename != None:
        if filename.endswith(".csv") or filename.endswith(".xlsx"):
            try:
                if filename.endswith(".csv"):
                    df = pd.read_csv(filename, dtype=object)
                elif filename.endswith(".xlsx"):
                    df = pd.read_excel(filename)
                df = df.fillna("")
                # If header column name is empty, rename it to ""
                df.columns = [
                    "" if re.match(r"^Unnamed: \d+$", col) else col
                    for col in df.columns
                ]
            except Exception as e: # If filename not found, create empty sheet
                df = pd.DataFrame({str(uuid.uuid4())[:8]: [traceback.format_exc()]})
            cache_df()
        else:
            mode = "Quit"
    else:
        mode = "Quit"
    # While key pressed isn't "q", continue executing
    while mode != "Quit":
        screen.clear()
        # Print Screen
        if mode == "Main":
            # Print Excel table
            print_df(df, posY, posX, cell_row_selection, cell_col_selection)
            # Print selected cell
            screen.addstr(0, 0, " "*num_cols) # Blank out row first to reset it
            # Print cell editor line
            if cell_row_selection == -1:
                print_data = str(df.columns[cell_col_selection])[:num_cols].replace('\n', '\\n')
            else:
                print_data = str(df.iloc[cell_row_selection, cell_col_selection])[:num_cols].replace('\n', '\\n')
            screen.addstr(0, 0, print_data, curses.A_BOLD)
        elif mode == "Cell":
            # Print Excel table
            print_df(df, posY, posX, cell_row_selection, cell_col_selection, mode="Cell")
            # Print selected cell
            screen.addstr(0, 0, " "*num_cols) # Blank out row first to reset it
            # Print cell editor line
            # Replace \n
            if cell_row_selection == -1:
                string_to_print = str(df.columns[cell_col_selection]).replace('\n', '\\n')
            else:
                string_to_print = str(df.iloc[cell_row_selection, cell_col_selection]).replace('\n', '\\n')
            if str(string_to_print) == "":
                screen.addstr(0, 0, " ", curses.color_pair(1))
            else:
                # If cell_editor_pos is -1, set it by default to the last character
                if cell_editor_char_pos == None:
                    cell_editor_char_pos = len(string_to_print) - 1
                # Determine start position
                if cell_editor_start_pos == -1:
                    cell_editor_start_pos = len(string_to_print) - num_cols + 1
                    if cell_editor_start_pos < 0:
                        cell_editor_start_pos = 0
                try:
                    screen.addstr(0, 0, string_to_print[cell_editor_start_pos:cell_editor_start_pos+num_cols], curses.color_pair(2) | curses.A_BOLD)
                except curses.error:
                    pass
                # Print cursor
                char_to_print = (string_to_print+" ")[cell_editor_char_pos + 1]
                try:
                    screen.addstr(0, cell_editor_char_pos-cell_editor_start_pos + 1, char_to_print, curses.color_pair(1))
                except curses.error:
                    pass
        elif mode == "Save" or mode == "Delete Row" or mode == "Delete Column":
            # Print normal table first
            print_df(df, posY, posX, cell_row_selection, cell_col_selection, mode=mode)
            try:
                screen.addstr(0, 0, " "*num_cols)
            except curses.error:
                pass
            try:
                screen.addstr(0, 0, str(df.iloc[cell_row_selection, cell_col_selection][:num_cols]).replace('\n', '\\n'), curses.A_BOLD)
            except curses.error:
                pass
            # Override save window over
            HALF_LENGTH = 15
            HALF_HEIGHT = 3
            if num_cols % 2 == 0:
                middle_col = int(num_cols / 2)
                window_left = middle_col - HALF_LENGTH
                window_right = middle_col + HALF_LENGTH
            else:
                middle_col = num_cols / 2
                window_left = int(middle_col - HALF_LENGTH - 0.5)
                window_right = int(middle_col + HALF_LENGTH + 0.5)
            if num_rows % 2 == 0:
                middle_row = int(num_rows / 2)
                window_top = middle_row - HALF_HEIGHT
                window_bot = middle_row + HALF_HEIGHT
            else:
                middle_row = num_rows / 2
                window_top = int(middle_row - HALF_HEIGHT - 0.5)
                window_bot = int(middle_row + HALF_HEIGHT + 0.5)
            # Draw corners
            screen.addstr(window_top, window_left, "┏", curses.color_pair(3) | curses.A_BOLD)
            screen.addstr(window_top, window_right, "┓", curses.color_pair(3) | curses.A_BOLD)
            screen.addstr(window_bot, window_left, "┗", curses.color_pair(3) | curses.A_BOLD)
            screen.addstr(window_bot, window_right, "┛", curses.color_pair(3) | curses.A_BOLD)
            # Draw sides
            for k in range(window_left+1, window_right):
                screen.addstr(window_top, k, "─", curses.color_pair(3) | curses.A_BOLD)
                screen.addstr(window_bot, k, "─", curses.color_pair(3) | curses.A_BOLD)
            for k in range(window_top+1, window_bot):
                screen.addstr(k, window_left, "│", curses.color_pair(3) | curses.A_BOLD)
                screen.addstr(k, window_right, "│", curses.color_pair(3) | curses.A_BOLD)
            # Blank out inside of box
            for row_i in range(window_top+1, window_bot):
                for col_i in range(window_left+1, window_right):
                    screen.addstr(row_i, col_i, " ")
            # Draw SAVE
            if mode == "Save":
                offset_left = 4
                button_left = "SAVE"
            elif mode == "Delete Row":
                offset_left = 4
                button_left = "YES"
            elif mode == "Delete Column":
                offset_left = 4
                button_left = "YES"
            if menu_selection == True:
                screen.addstr(window_bot - 2, window_left + offset_left, button_left, curses.color_pair(1))
            else:
                screen.addstr(window_bot - 2, window_left + offset_left, button_left)
            # Draw BACK
            if mode == "Save":
                offset_right = 3 + 10
                button_right = "DON'T SAVE"
            elif mode == "Delete Row":
                offset_right = 5
                button_right = "NO"
            elif mode == "Delete Column":
                offset_right = 5
                button_right = "NO"
            if menu_selection == False:
                screen.addstr(window_bot - 2, window_right - offset_right, button_right, curses.color_pair(1))
            else:
                screen.addstr(window_bot - 2, window_right - offset_right, button_right)
            # Draw question
            if mode == "Save":
                question = "Exit and ..."
            elif mode == "Delete Row":
                question = "Delete Row?"
            elif mode == "Delete Column":
                question = "Delete Column?"
            else:
                question = "Are you sure?"
            screen.addstr(window_top + 2, window_left + 4, question, curses.color_pair(4) | curses.A_BOLD)

        # Handle key presses based on mode
        if mode == "Main":
            screen.refresh()
            curses.flushinp()
            key = screen.getch()
            if key == 87: # Shift+W
                # Add row before
                df1 = df.iloc[:cell_row_selection]
                df2 = df.iloc[cell_row_selection:]
                df_new = pd.DataFrame(columns=df.columns)
                df_new.loc[len(df_new)] = ""
                df = pd.concat([df1, df_new, df2], ignore_index=True)
                cache_df()
            elif key == 83: # Shift + S
                # Add row after
                df1 = df.iloc[:cell_row_selection+1]
                df2 = df.iloc[cell_row_selection+1:]
                df_new = pd.DataFrame(columns=df.columns)
                df_new.loc[len(df_new)] = ""
                df = pd.concat([df1, df_new, df2], ignore_index=True)
                key = curses.KEY_DOWN # Move cursor down
                cache_df()
            elif key == "": # ??
                # Delete row
                pass
            elif key == 65: # Shift + A
                # Add column before
                new_colname = str(uuid.uuid4())[:8]
                while new_colname in df.columns:
                    new_colname = str(uuid.uuid4())[:8]
                df.insert(cell_col_selection, new_colname, "")
                cache_df()
            elif key == 68: # Shift + D
                # Add column after
                new_colname = str(uuid.uuid4())[:8]
                while new_colname in df.columns:
                    new_colname = str(uuid.uuid4())[:8]
                df.insert(cell_col_selection+1, new_colname, "")
                key = curses.KEY_RIGHT # Move cursor right
                cache_df()
            elif key == 60: # <
                undo_df()
            elif key == 62:
                redo_df()

            if key == curses.KEY_UP or key == 119: # Up arrow key
                key_up()
            elif key == curses.KEY_DOWN or key == 115: # Down arrow key
                key_down()
            elif key == curses.KEY_LEFT or key == 97: # Left arrow key
                key_left()
            elif key == curses.KEY_RIGHT or key == 100: # Right arrow key
                key_right()
            elif key == curses.KEY_DC: # Delete key deletes row if selecting row, else deletes column if selecting header
                if cell_row_selection >= 0:
                    menu_selection = False
                    mode = "Delete Row"
                elif cell_row_selection == -1:
                    menu_selection = False
                    mode = "Delete Column"
            elif key == 10: # Enter
                cell_editor_char_pos = None # Reset cell editor cursor
                cell_editor_start_pos = -1
                mode = "Cell"
            elif key == 113 or key == 81: # q/Q
                mode = "Save"
                menu_selection = True
            # Test code for when you want to verify what number the key is
            else:
                screen.addstr(14, 14, str(key), curses.A_UNDERLINE)
                screen.refresh()
                curses.napms(500)
        elif mode == "Cell":
            screen.refresh()
            curses.flushinp()
            key = screen.getch()
            if key == 27 or key == 10: # Esc or Enter
                cache_df()
                mode = "Main"
            elif key == curses.KEY_LEFT:
                if cell_editor_char_pos > -1:
                    cell_editor_char_pos -= 1
                    if cell_editor_char_pos < cell_editor_start_pos and cell_editor_start_pos > 0:
                        cell_editor_start_pos -= 1
            elif key == curses.KEY_RIGHT:
                if cell_row_selection == -1:
                    string_to_print = str(df.columns[cell_col_selection]).replace('\n', '\\n')
                else:
                    string_to_print = str(df.iloc[cell_row_selection, cell_col_selection]).replace('\n', '\\n')
                if cell_editor_char_pos < len(string_to_print) - 1:
                    cell_editor_char_pos += 1
                    if cell_editor_char_pos > cell_editor_start_pos + num_cols - 2:
                        cell_editor_start_pos += 1
            elif key == curses.KEY_BACKSPACE or key == 127 or key == '\\b' or key == 8: # Handler for Backspace
                if cell_editor_char_pos != None:
                    if cell_editor_char_pos > -1:
                        if cell_row_selection == -1:
                            string_to_edit = df.columns[cell_col_selection]
                            df.rename(columns={df.columns[cell_col_selection]: string_to_edit[:cell_editor_char_pos]+string_to_edit[cell_editor_char_pos+1:]}, inplace=True)
                        else:
                            string_to_edit = df.iloc[cell_row_selection, cell_col_selection]
                            df.iloc[cell_row_selection, cell_col_selection] = string_to_edit[:cell_editor_char_pos]+string_to_edit[cell_editor_char_pos+1:]
                        cell_editor_char_pos -= 1
            elif key == curses.KEY_DC: # Handler for Delete
                if cell_editor_char_pos != None:
                    if cell_row_selection == -1:
                        string_to_edit = df.columns[cell_col_selection]
                        if cell_editor_char_pos < len(string_to_edit) - 1:
                            df.rename(columns={df.columns[cell_col_selection]: string_to_edit[:cell_editor_char_pos+1]+string_to_edit[cell_editor_char_pos+2:]}, inplace=True)
                    else:
                        string_to_edit = df.iloc[cell_row_selection, cell_col_selection]
                        if cell_editor_char_pos < len(string_to_edit) - 1:
                            df.iloc[cell_row_selection, cell_col_selection] = string_to_edit[:cell_editor_char_pos+1]+string_to_edit[cell_editor_char_pos+2:]
            elif key in valid_chars: # Handler for typable characters
                if cell_editor_char_pos == None:
                    string_to_edit = ""
                    cell_editor_char_pos = -1
                else:
                    if cell_row_selection == -1:
                        string_to_edit = df.columns[cell_col_selection]
                    else:
                        string_to_edit = df.iloc[cell_row_selection, cell_col_selection]
                if string_to_edit == None:
                    string_to_edit = ""
                if cell_editor_char_pos == -1:
                    if cell_row_selection == -1:
                        df.rename(columns={df.columns[cell_col_selection]: chr(key) + string_to_edit}, inplace=True)
                    else:
                        df.iloc[cell_row_selection, cell_col_selection] = chr(key) + string_to_edit
                    cell_editor_char_pos += 1
                else:
                    if cell_row_selection == -1:
                        df.rename(columns={df.columns[cell_col_selection]: string_to_edit[:cell_editor_char_pos+1] + chr(key) + string_to_edit[cell_editor_char_pos+1:]}, inplace=True)
                    else:
                        df.iloc[cell_row_selection, cell_col_selection] = string_to_edit[:cell_editor_char_pos+1] + chr(key) + string_to_edit[cell_editor_char_pos+1:]
                    cell_editor_char_pos += 1
                    if cell_editor_char_pos > cell_editor_start_pos + num_cols - 2:
                        cell_editor_start_pos += 1
        elif mode == "Save" or mode == "Delete Row" or mode == "Delete Column":
            screen.refresh()
            curses.flushinp()
            key = screen.getch()
            if key == curses.KEY_LEFT or key == 97:
                menu_selection = not menu_selection
            elif key == curses.KEY_RIGHT or key == 100:
                menu_selection = not menu_selection
            elif key == 10: # Enter
                # Handler for save menu
                if mode == "Save":
                    if menu_selection == True: # Quit and Save
                        if filename.endswith(".csv"):
                            df.to_csv(filename, index=False)
                        elif filename.endswith(".xlsx"):
                            df.to_excel(filename, index=False)
                        mode = "Quit"
                    elif menu_selection == False: # Quit and don't save
                        mode = "Quit"
                elif mode == "Delete Row":
                    # Handler for delete row menu
                    if menu_selection == True:
                        df1 = df.iloc[:cell_row_selection]
                        df2 = df.iloc[cell_row_selection+1:]
                        df = pd.concat([df1, df2], ignore_index=True)
                        if len(df.index) != 0:
                            if cell_row_selection > len(df.index) - 1:
                                key_up()
                        else:
                            df.loc[len(df)] = "" * len(df.columns)
                        cache_df()
                        mode = "Main"
                    elif menu_selection == False:
                        mode = "Main"
                elif mode == "Delete Column":
                    # Handler for Delete Column menu
                    if menu_selection == True:
                        if len(df.columns) > 1:
                            df.drop(columns=df.columns[cell_col_selection], inplace=True)
                        else:
                            df = pd.DataFrame({str(uuid.uuid4())[:8]: [""]})
                        if cell_col_selection > len(df.columns) - 1:
                            key_left()
                        cache_df()
                        mode = "Main"
                    elif menu_selection == False:
                        mode = "Main"
            elif key == 27 or key == curses.KEY_BACKSPACE or key == 127 or key == '\\b' or key == 8: # Esc or Backspace
                mode = "Main"
    end_program()
except Exception as e:
    end_program()
    print("Exception occured:", e)
    traceback.print_exc()