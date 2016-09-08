__author__ ='Rahul Chatterjee'
import os, sys
import tarfile, gzip
import itertools
import string
import bz2

THIS_DIR = os.path.dirname(__file__)
DATA_DIR_PATH = os.path.join(THIS_DIR, 'data/')

MIN_PROB = 1e-8  # default probability of a password, if not found in the dict.
MIN_LENGHT_PW = 6   # Only consider passwords with length 6 or more

# A filter to not consider passwords that are not ascii only, or shorter than
# 6 characters
PW_FILTER = lambda x: is_asciistring(x) and len(x)>=MIN_LENGHT_PW

user_friendly = 0
BLANK = [b'\x00', b'*'][user_friendly]   # '\b'
STARTSTR = [b'\x01', '^'][user_friendly]
ENDSTR = [b'\x02', b'$'][user_friendly]

SHIFT_KEY = [b'\x03', b"<s>"][user_friendly]
CAPS_KEY = [b'\x04', b"<c>"][user_friendly]

ALLOWED_KEYS = b"`1234567890-=qwertyuiop[]\\asdfghjkl;'zxcvbnm,./ "
ALLOWED_CHARACTERS = string.ascii_letters + string.digits + string.punctuation + ' ' # removed tab

# ALLOWED_KEYS += BLANK +  + STARTSTR + ENDSTR + SHIFT_KEY + CAPS_KEY
ALLOWED_KEYS += SHIFT_KEY + CAPS_KEY

### Future work to do it on ALLOWED_KEYS ##
ALLOWED_CHARACTERS += str(BLANK + STARTSTR + ENDSTR)

def dp(**kwargs):
    print(
        '\n',
        '\t'.join("%s: %s" % (k,str(v)) \
                  for k,v in kwargs.items())
    )


## All allowed correctors
ALLOWED_EDITS = [
    'same',      # 1, 
    'swc-all',   # 2
    'swc-first', # 4
    'rm-lastc',  # 3
    'rm-firstc', # 10
    'rm-lasts',  # 3
    'cap2up',    # 5
    'upncap',  # 6
    'rm-lastd',  # 6
    'rm-lastl',  # 7
    'sws-last1', # 8
    'sws-lastn', # 9
    'add1-last', # 11
    'up2cap',    # 12
    'n2s-last',  # 13
    'keypress-edit', # 14
]

top2correctors = ['same', 'swc-all', 'swc-first']
top3correctors = ['same', 'swc-all', 'swc-first', 'rm-lastc']
top5correctors = ['same', 'swc-all', 'swc-first', 'rm-lastc',
                  'rm-firstc', 'n2s-last']

home= os.path.expanduser('~')

## Number of passwords fixed by each correctors
TYPO_FIX_PROB = {
    "rm-lastl": 59, 
    "rm-firstc": 55, 
    "swc-all": 1698, 
    "sws-lastn": 14, 
    "rm-lastd": 60, 
    "upncap": 13, 
    "same": 90234, 
    "swc-first": 209, 
    "sws-last1": 19, 
    "cap2up": 5, 
    "n2s-last": 9, 
    "add1-last": 5, 
    "rm-lasts": 72,
    "kclose": 1385,
    "other": 1918,
    "tcerror": 18,
    "rm-lastc": 191,
    "keypress-edit":1000
}




################################################################################
## General functions
################################################################################

def getallgroups(arr, k=-1):
    """
    returns all the subset of @arr of size less than equalto @k
    the return array will be of size \sum_{i=1}^k nCi, n = len(arr)
    """
    if k<0:
        k = len(arr)
    return itertools.chain.from_iterable(itertools.combinations(set(arr), j)
                                    for j in range(1,k+1))

def is_asciistring(s):
    return all(ord(c)<128 for c in s) # python 3
    # python 2 version
    if not isinstance(s, str):
        return False
    try:
        s.decode('ascii')
        return True
    except (UnicodeDecodeError, UnicodeEncodeError) as e:
        # warning("UnicodeError:", s, str(e))
        return False

def get_most_val_under_prob(A, probs, p_cutoff):
    """Brute force find optimal subset of A, such that total weight of B
    is less than p_cutoff

    """
    assert len(A)<10, "Not going to work for large sets, len(A)={}".format(A)
    try:
        return max(filter(lambda x: sum(probs.get(a) for a in x)<=p_cutoff, getallgroups(A.keys())),
               key=lambda x: sum(A[y] for y in x))
    except ValueError:
        return []


def fname2leakname(fname):
    """
    Filename should be "<leakname>-anygibbersih.[tar.gz|txt]"
    """
    return os.path.basename(fname).split('.')[0].split('-')[0]

def file_type(filename):
    """returns the type of the file"""
    magic_dict = {
        "\x1f\x8b\x08": "gz",
        "\x42\x5a\x68": "bz2",
        "\x50\x4b\x03\x04": "zip"
    }
    max_len = max(len(x) for x in magic_dict)
    with open(filename) as f:
        file_start = f.read(max_len)
    for magic, filetype in magic_dict.items():
        if file_start.startswith(magic):
            return filetype
    return "no match"

def open_(filename, mode='r'):
    """Wrapper over normal python open, that opens compressed
    files in format such as bz2, gz, etc.
    """
    print(__func__, filename)
    if mode=='w':
        type_ = filename.split('.')[-1]
    else:
        type_ = file_type(filename)
    if type_ == "bz2":
        f = bz2.BZ2File(filename, mode)
    elif type_ == "tar":
        f = tarfile.open(filename, mode)
    elif type_ == "gz":
        f = gzip.GzipFile(filename, mode)
    else:
        f = open(filename, mode);
    return f;


def get_line(file_object, limit=-1, pw_filter=lambda x: True):
    regex = re.compile(r'\s*([0-9]+) (.*)$')
    i = 0
    for l in file_object:
        if limit>0 and limit<=i:
            break
        m = regex.match(l)
        if not m:
            warning ("REGEX FAIL: ", l)
        c, w = m.groups()
        c = int(c)
        w = w.replace('\x00', '\\x00')
        try:
            w = w.decode('utf-8', errors='replace')
        except UnicodeDecodeError:
            #try with latin1
            warning("Error in decoding: ({} {}). Line: {}. Ignoring!"\
                    .format(w, c, l))
            continue
        if w and pw_filter(w) and c>0:
            i += 1
            yield w,c
        else:
            pass
            #warning ("Filter Failed or malformed string: ", w, c)


def open_get_line(filename, limit=-1, **kwargs):
    with open_(filename) as f:
        for w,c in get_line(f, limit, **kwargs):
            yield w, c



