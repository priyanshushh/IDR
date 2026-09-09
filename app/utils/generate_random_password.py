import random
import string

def generate_random_password():
    length = 8
    password = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))
    return password
    