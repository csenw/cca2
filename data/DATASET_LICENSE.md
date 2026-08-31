# Dataset attribution

The release dataset is derived from **SQuAD 1.1 (Stanford Question Answering Dataset)**.

- Project page: https://rajpurkar.github.io/SQuAD-explorer/
- Original paper: Rajpurkar, Zhang, Lopyrev, and Liang, *SQuAD: 100,000+ Questions for Machine Comprehension of Text* (2016).
- License: **CC BY-SA 4.0**
- License text: https://creativecommons.org/licenses/by-sa/4.0/

For this assignment, course staff perform sentence-aware chunking, whitespace normalization,
empty-chunk removal, deterministic sampling, and stable document-ID assignment. Students may
apply additional text-level preprocessing in the notebook, provided that document IDs and the
one-document-to-one-vector mapping are preserved.
