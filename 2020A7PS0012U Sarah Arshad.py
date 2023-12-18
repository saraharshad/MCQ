import streamlit as st
import re
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

API_KEY = "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"

llm = OpenAI(openai_api_key=API_KEY, temperature=0.9)

prompt_template = PromptTemplate(
    template="Generate at least {num_questions} multiple-choice questions based on {topic}. Incorporate the following structure: 'Q:' for the question, which ends with '?', in the next line the options starting with 'A)', and finally the answer starting with 'Answer'.",
    input_variables=['topic', 'num_questions']
)

mcq = LLMChain(
    llm=llm,
    prompt=prompt_template,
    verbose=True
)

def generate_quiz():
    st.title("MCQ Quiz Application")
    user_prompt = st.text_input("Enter a topic for your quiz")
    num_questions = st.number_input("Enter the number of questions", min_value=1, max_value=10, value=5)

    quiz_started = False
    quiz_submitted = False

    if st.button("Generate quiz") and user_prompt and num_questions:
        quiz_started = True

    if quiz_started:
        session_state = st.session_state.setdefault('user_answers', [])
        quiz_data = []

        with st.spinner():
            output = mcq.run(topic=user_prompt, num_questions=num_questions)

            # Regular expressions to extract questions, options, and answers
            matches = re.findall(r'Q:\s*(.*\?)\s*A\)\s*(.*?)\s*B\)\s*(.*?)\s*C\)\s*(.*?)\s*D\)\s*(.*?)\s*Answer:\s*(.*)', output, re.DOTALL)
            if matches:
                correct_answers = [match[5] for match in matches]

                for idx, match in enumerate(matches, start=1):
                    question = match[0]
                    options = match[1:5]
                    answer = match[5]

                    # Store question, options, and answer data
                    quiz_data.append({"question": question, "options": options, "answer": answer})

                # Display questions and options
                for idx, data in enumerate(quiz_data, start=1):
                    st.write(f"Question {idx}: {data['question']}")
                    user_selected = st.radio(f"Select an answer for Question {idx}:", options=data['options'], key=f"{idx}")

                    # Store user selections
                    if len(session_state) >= idx:
                        session_state[idx - 1] = user_selected
                    else:
                        session_state.append(user_selected)
                
                # Submit button to calculate and display score
                if st.button("Submit"):
                    quiz_submitted = True
                    st.write("User Answers:")
                    st.write(session_state)
                    
                    if len(session_state) == num_questions:
                        # Calculate score
                        correct_count = sum(user_ans == correct_ans for user_ans, correct_ans in zip(session_state, correct_answers))
                        st.write(f"You got {correct_count} out of {num_questions} correct!")
                        st.write("Correct Answers:")
                        for idx, correct_answer in enumerate(correct_answers, start=1):
                            st.write(f"Question {idx}: {correct_answer}")
                    else:
                        st.write("Please answer all questions before submitting.")

generate_quiz()



