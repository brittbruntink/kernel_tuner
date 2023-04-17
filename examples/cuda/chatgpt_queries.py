chatGPT_queries = {
    "start": lambda kernel_string:
        f"""
        """,
    "vary_work_per_thread" : {
        "Initial_2elem": lambda kernel_string:
            f"""
            Rewrite the following CUDA code:
            {kernel_string}.
            Do not change the argument list of the kernel.
            First write "START", then write the rewritten kernel and write "END" straight after the kernel. """,
        "Tunable_nr_elem": lambda:
            f"""
            Please rewrite the code introducing a for loop to allow the number of elements processed by each thread to vary. This number is specified using a C preprocessor defined constant? Please call this constant 'tile_size_x' in lower case. You can omit the definition of this C preprocessor constant.
            """,
        "Incorrect_kernel": lambda:
            f"""
            This kernel does not produce the correct result, can you try again?
            """,
        "Markdown_response": lambda:
            f"""
            Thank you, the response is in markdown, can you make it a code block?
            """,
        "Fails_to_compile": lambda:
            f"""
            This kernel does not compile for me, can you try again?
            """,
    }
}
