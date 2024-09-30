"""
The MIT License (MIT)

Copyright (c) 2024-present Developer Anonymous

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""
# Simple code that must only be run when wanting to make the code prettier

try:
    import black
    import autoflake
except ImportError as exc:
    raise RuntimeError('Cannot use the prettier without black and autoflake installed') from exc

del black, autoflake  # Not used anyways

import os

def run_black():
    os.system('python -m black bot.py models.py cogs _types')

def run_autoflake():
    files = ['bot.py', 'models.py']

    for directory in ('cogs', 'sessions', '_types'):
        for file in os.listdir(directory):
            if file.endswith('.pyi'):
                continue
            if file.endswith('.py'):
                files.append(f'{directory}/{file}')
            else:
                for subfile in os.listdir(f'{directory}/{file}'):
                    # We iterate up to this level, any files in subfolders are ignored
                    if subfile.endswith('.py'):
                        files.append(f'{directory}/{file}/{subfile}')

    print(f'Files that are going to be formatted: {", ".join(files)}')
    os.system(f'python -m autoflake {" ".join(files)}')

run_black()
run_autoflake()
