from metacall import metacall_load_from_file, metacall

def add(a, b):
    print("Adding")
    return a + b

def multiply_via_js(a, b):
    print("Multiplt VIA JS")
    metacall_load_from_file('node', ['functions.js'])
    return metacall('js_multiply', a, b)

def complex_calc(a, b):
    print("Complex CALC")
    metacall_load_from_file('node', ['functions.js'])  # load once ideally
    added = add(a, b)
    return metacall('js_multiply', added, b)

# if __name__ == "__main__":
#     print("START")
#     print(complex_calc(3, 4))