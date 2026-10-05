# Sample inputs

Each file is one LAMBDA constructor expression (comments allowed). Load the
canned examples from the page, or use **Choose File…** for any file here.

| File | Lint | Interpret | Demonstrates |
| --- | --- | --- | --- |
| `factorial.txt` | ok | `D0Vint(arg1=3628800)` | Canned example (F1) |
| `fibonacci.txt` | ok | `D0Vint(arg1=55)` | Canned example (F1) |
| `undeclared-variable.txt` | language error: `y` | runtime error | Lint finds undeclared names (F5) |
| `division-by-zero.txt` | ok | runtime error (`ZeroDivisionError`) | Lint passing ≠ evaluation succeeding (F6) |
| `malformed-input.txt` | input error | input error | Invalid input reported, nothing runs (F6) |
| `rejected-code.txt` | input error | input error | Restricted reader never executes Python |
| `html-like-text.txt` | language error: `<i>x</i>` | runtime error | Text shown literally, never as markup (F9) |
| `slow-fibonacci.txt` | ok | backend failure: timed out after 5 s | Bounded execution, then retry (F10) |
| `invalid-utf8.txt` | — | — | Upload rejected as invalid UTF-8; previous source kept (F3) |
