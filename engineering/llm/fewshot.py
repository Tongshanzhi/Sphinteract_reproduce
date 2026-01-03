def get_few_shot_examples(vectorstore, target_nlq, n_shots=3):
    if not vectorstore or n_shots <= 0:
        return ""
    try:
        docs = vectorstore.similarity_search(target_nlq, k=n_shots)
        examples = []
        for doc in docs:
            nl = doc.metadata.get('nl', '')
            gold = doc.metadata.get('gold', '')
            if nl and gold:
                examples.append(f"/* Example */\n/* Question: {nl} */\n/* SQL: */\n{gold}")
        if examples:
            return "/* some examples are provided */\n" + "\n\n".join(examples) + "\n\n"
        return ""
    except Exception as e:
        print(f"Error retrieving examples: {e}")
        return ""

def get_feedback_few_shot_examples(vectorstore, target_nlq, n_shots=3):
    if not vectorstore or n_shots <= 0:
        return ""
    try:
        docs = vectorstore.similarity_search(target_nlq, k=n_shots)
        examples = []
        for doc in docs:
            nl = doc.metadata.get('nl', '')
            gold = doc.metadata.get('gold', '')
            fb = doc.metadata.get('feedback', '')
            if nl and gold and fb:
                examples.append(f"\nExample Question: {nl}\nExample Feedback:{fb}\nExample Answer: {gold}")
        if examples:
            return "/* some examples are provided */\n" + "".join(examples) + "\n\n"
        return ""
    except Exception as e:
        print(f"Error retrieving feedback examples: {e}")
        return ""

