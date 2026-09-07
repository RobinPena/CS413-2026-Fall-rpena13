In this short exercise, we noted that the AI did as we could have expected from such a short program.  A handful of differences were noted during the translation due to differences between 
languages. To name some of them: 

- No-newline print → aprint helper. ATS's print does not append a trailing newline, and Python’s does by default. 

- Recursion limit raised since ATS guarantees proper tail-call optimization for the self-tail-recursive search and CPython has no TCO.
 
- Python has no static tuple-arity types, so the board is just a plain 8-tuple of ints used directly, with no named type alias.

- Minor syntax translations, not behavioral changes. 

To understand that the program worked as intended, I had to familiarize myself with both the puzzle and the ATS language, which I had never heard of until this class.  AI cut the time needed for such a problem. It would have been doable regardless, but not knowing the source language would have made it harder to maintain as much similarity as possible. The ability to quickly produce the code and then debug and check for any redundancy improves the building code workflow. Nevertheless, it does feel a little cheap, but I guess that would change as this new age of AI becomes the new normal.
