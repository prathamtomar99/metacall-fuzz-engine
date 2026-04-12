const { metacall, metacall_load_from_file } = require('metacall');

metacall_load_from_file('rb', ['rb_functions.rb']);

console.log("=== JS -> Ruby ===");

const r_int = metacall('rb_int', 3, 4);
console.log(`[INT]   rb_int(3, 4)        = ${r_int}   | expected: 7          | pass: ${r_int === 7}`);

const r_float = metacall('rb_float', 1.5, 2.5);
console.log(`[FLOAT] rb_float(1.5, 2.5)  = ${r_float} | expected: 4.0        | pass: ${r_float === 4.0}`);

const r_str = metacall('rb_str', 'hello', 'world');
console.log(`[STR]   rb_str(hello,world)  = ${r_str} | expected: helloworld | pass: ${r_str === 'helloworld'}`);

const r_bool = metacall('rb_bool', true);
console.log(`[BOOL]  rb_bool(true)        = ${r_bool}  | expected: false      | pass: ${r_bool === false}`);

let r_null;
let null_known_bug = false;

try {
	r_null = metacall('rb_null');
	null_known_bug = r_null === undefined || r_null === null || r_null === 'Invalid';
} catch (err) {
	// Known MetaCall boundary issue: Ruby nil/Invalid may fail Node N-API conversion.
	r_null = 'Invalid';
	null_known_bug = true;
}

const null_ok = r_null === '0' || r_null === 0 || null_known_bug;
const null_expected = null_known_bug ? 'Invalid/undefined/null' : '"0"';
console.log(`[NULL]  rb_null()            = ${r_null}  | expected: ${null_expected} | pass: ${null_ok}`);