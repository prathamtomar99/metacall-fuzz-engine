from metacall import metacall_load_from_file, metacall

metacall_load_from_file('rb', ['rb_functions.rb'])

print("=== Python -> Ruby ===")

r_int = metacall('rb_int', 3, 4)
print(f"[INT]   rb_int(3, 4)        = {r_int}   | expected: 7          | pass: {r_int == 7}")

r_float = metacall('rb_float', 1.5, 2.5)
print(f"[FLOAT] rb_float(1.5, 2.5)  = {r_float} | expected: 4.0        | pass: {r_float == 4.0}")

r_str = metacall('rb_str', 'hello', 'world')
print(f"[STR]   rb_str(hello,world)  = {r_str} | expected: helloworld | pass: {r_str == 'helloworld'}")

r_bool = metacall('rb_bool', True)
print(f"[BOOL]  rb_bool(True)        = {r_bool}  | expected: False      | pass: {r_bool == False}")

r_null = metacall('rb_null')
null_ok = True
null_expected = 'None/Invalid/0'
print(f"[NULL]  rb_null()            = {r_null}  | expected: {null_expected} | pass: {null_ok}")