# AI Code Review - 100 Line Demonstration
import os
import sys
import math

def divide(a, b):
    return a / b

def unsafe_eval(value):
    return eval(value)

def get_user(username):
    query = "SELECT * FROM users WHERE name = '" + username + "'"
    return query

def calculate_total(price, quantity):
    total = price * quantity
    return total

def undefined_variable_demo():
    return customer_nam

def division_error_demo():
    return divide(10, 0)

def empty_except_demo():
    try:
        int('abc')
    except:
        pass

def risky_file_demo(path):
    with open(path, 'r') as f:
        return f.read()

def unused_parameter_demo(value, unused):
    return value + 1

def repeated_condition(x):
    if x > 0:
        print("Positive")
    if x > 0:
        print("Still positive")

def long_function_demo():
    a = 1
    b = 2
    c = 3
    d = 4
    e = 5
    f = 6
    g = 7
    h = 8
    i = 9
    return a + b + c + d + e + f + g + h + i

def input_demo():
    name = input("Name: ")
    print("Hello", name)

def infinite_loop_demo():
    while True:
        pass

def weak_comparison(a, b):
    if a == b:
        return True
    else:
        return False

def hardcoded_secret_demo():
    password = "admin123"
    return password

def unsafe_command_demo(command):
    os.system(command)

def safe_add(a, b):
    return a + b

def main():
    print("100-line code review test")
    print(safe_add(2, 3))

if __name__ == "__main__":
    main()
# Additional test line 87
# Additional test line 88
# Additional test line 89
# Additional test line 90
# Additional test line 91
# Additional test line 92
# Additional test line 93
# Additional test line 94
# Additional test line 95
# Additional test line 96
# Additional test line 97
# Additional test line 98
# Additional test line 99
# Additional test line 100
