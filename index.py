import openai
import streamlit as st
import random
from langchain.llms import OpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import keys

# openai.organization = keys.OPENAI_ORG
openai.api_key = keys.OPENAI_KEY
llm = OpenAI(openai_api_key=openai.api_key, temperature=0.9)

prompt_template = PromptTemplate(
    template="Generate a 1000 word essay on the topic {topic}, keep in mind this essay should have many quiz related facts. These facts will later be used to generate quiz questions.",
    input_variables=['topic']
)

agent = LLMChain(
    llm=llm,
    prompt=prompt_template,
    verbose=True
)
#To mark and save the correct answers
CORRECT_MARK = "^"
### Functions
#OpenAI chat Completion API
def get_openai_completion(prompt):
    print('\n\nOPENAI-PROMPT:', prompt)
    try:
        res = openai.Completion.create(engine="text-davinci-003", prompt=prompt, max_tokens=400, temperature=0.1)
        print('\n\nOPENAI-RESPONSE:', res)
        return res.choices[0]['text'] or None
    except Exception as e:
        print(f'get_openai_completion - exception: ', e)
        st.write(e)

@st.cache_data
def openai_get_questions(input_text, questions_number=3, response_options_number=3):
    questions_number = st.session_state["num_question"]
    prompt_v3 = f'''Ask {questions_number} multi-choice questions to the following text. Each question should have {response_options_number} answer options. Mark the correct answer with "{CORRECT_MARK}" at the end:
    {input_text}
    '''
    return get_openai_completion(prompt_v3)

# removes the leading "Q1: " for questions,
# or "A. " for response options,
# or "1. " for proofs; might not be 100% reliable
def remove_string_identifier(raw_q):
    parts = raw_q.split(' ')
    without_q_number = parts[1:]
    return ' '.join(without_q_number)

# in some queries to OpenAI all multi-choice questions
# generated had correct answer as the 1st option - not good
def shuffle_options(options, old_correct_idx):
    correct_option = options[old_correct_idx]
    randomised_options = random.sample(options, len(options))
    new_correct_idx = randomised_options.index(correct_option)
    return randomised_options, new_correct_idx

# Expects a string like
# "\n\nQ1: The 1st question?\nA. Option A, marked as correct with^\nB. The 2nd answer\nC. There may be 3-4 options\n\nQ2: Question #2\nA. ...."
# Returns an array of question objects (with keys questions, options, reference, correct_option_index, was_answered, was_skipped)
def openai_res_to_questions(openai_resp_questions):
    res = []
    leading_trailing_new_lines_removed = openai_resp_questions.strip('\n')
    paragraphs = leading_trailing_new_lines_removed.split('\n\n')
    
    for paragraph in paragraphs:
        if not paragraph: continue
        parts = paragraph.split('\n')
        the_question = remove_string_identifier(parts[0]) # remove leading "Q1: " or "1. "
        options_with_numbers = parts[1:]
        options = [remove_string_identifier(option) for option in options_with_numbers] # remove eg "A. "
        options_randomised = random.sample(options, len(options)) # sometimes all the questions may have correct answer at idx 0
        q = {}
        for idx, el in enumerate(options_randomised):
            if CORRECT_MARK in el:
                q['correct_option_index'] = idx
                options_randomised[idx] = el.replace(CORRECT_MARK, '').rstrip()
        q['question'] = the_question
        q['options'] = options_randomised
        q['was_answered'] = False
        q['was_skipped'] = False
        res.append(q)
    return res

# Gets the list of objects with questions and answer options,
# returns a list of correct options (to be used for fetching proofs)
def extract_correct_answers(questions):
    res = []
    for question in questions:
        correct_option_idx = question['correct_option_index'] # starts from 0
        correct_option = question['options'][correct_option_idx]
        res.append(correct_option)
    print('[extract_correct_answers]:\n', res)
    return res

#Generates an essay on the topic
def langchain_get_essay(user_input):
    essay = agent.run(topic=user_input)
    print(essay)
    return essay
# Gets the text pasted by the user, does pre-processing (if needed), 
# generates questions using OpenAI API

#Format:
# {
#     "questions": [
#         {
#             "question": "What is prompt engineering?",
#             "options": [
#                 "The art of writing good intentional prompts that produce an output from a generative AI model",
#                 "A more abstract version of programming",
#                 "A super abstract programming of an AI model",
#                 "A way to modify the mode or type of task that has been formed"
#             ],
#             "correct_option_index": 0,
#             "was_answered": false,
#             "was_skipped": false
#         },
#         {
#             "question": "What is the best way to think about prompt engineering?",
#             "options": [
#                 "As a way to modify the mode or type of task that has been formed",
#                 "As a more abstract version of programming",
#                 "As a super abstract programming of an AI model",
#                 "As the next step in programming languages"
#             ],
#             "correct_option_index": 1,
#             "was_answered": false,
#             "was_skipped": false
#         }
#     ]
# }
def get_questions(user_input):
    print('\n\n>>LOADING DATA')
    user_input = langchain_get_essay(user_input)
    openai_questions = openai_get_questions(user_input)
    questions = openai_res_to_questions(openai_questions)
    return { 'questions': questions }

def generate_response_options_states(questions):
    response_options_state = {}
    for idx, question in enumerate(questions, start=1):
        question_index = f'q{idx}'
        response_options_state[question_index] = {}
        for op_idx, _ in enumerate(question['options'], start=1):
            response_options_state[question_index][str(op_idx)] = { 'selected': 0, 'disabled': 0 }
        skip_key = f'skip_{question_index}'
        response_options_state[question_index][skip_key] = { 'selected': 0, 'disabled': 0 }
    return response_options_state

def initialize_state(user_input):
    initilized = 'initilized' in st.session_state and st.session_state['initilized']
    if initilized:
        return
    st.session_state['user_score'] = 0
    questions = get_questions(user_input)
    st.session_state['questions'] = questions
    options = generate_response_options_states(questions['questions'])
    st.session_state['options_state'] = options
    st.session_state['questionnaire_state'] = { 'questions_asked': [], 'questions_skipped': [], 'correct': [] }
    st.session_state['initilized'] = True

def renderQuestions():
    def disable_options(question_options_state_keys):
        for question_option in question_options_state_keys:
            question_options_state_keys[question_option]['disabled'] = True
        
    # q_idx - the number part of the key in session_state['options_state'], eg. 1 (to be transformed into 'q1')
    # option_key_to_select - the name of the option key, which needs to be marked as key.selected = true, eg '1' or 'skip_q2'
    def mark_selected(q_idx, option_key_to_select):
        q_index_key = f'q{q_idx+1}'
        for option in st.session_state['options_state'][q_index_key]:
            if option == option_key_to_select:
                st.session_state['options_state'][q_index_key][option]['selected'] = True
            else:
                st.session_state['options_state'][q_index_key][option]['selected'] = False
        
    # q_idx = 0, index in session_state['questions']['questions']
    # q_state_key = {'1': {'selected': 0, 'disabled': 0}, '2': {'selected': 0, 'disabled': 0}, ...}
    # opt_idx_to_select: number = 2
    def mark_selected_disable_all_options(q_idx, q_state_key, option_key_to_select):
        mark_selected(q_idx, option_key_to_select)
        disable_options(q_state_key)

          
    # q_idx - question index (start=1), e.g. 1 for the 1st question (with index 0)
    # answer_status - enum('skipped', 'correct', 'wrong')
    #  st.session_state.questionnaire_state = { 'questions_asked': [], 'questions_skipped': [], 'correct': [] }
    def update_score(q_idx, answer_status='wrong'):
        if q_idx not in st.session_state['questionnaire_state']['questions_asked']:
            st.session_state['questionnaire_state']['questions_asked'].append(q_idx)
            if answer_status == 'skipped':
                st.session_state['questionnaire_state']['questions_skipped'].append(q_idx)
            elif answer_status == 'correct':
                st.session_state['questionnaire_state']['correct'].append(q_idx)
    
    def show_stats():
        questions_asked = len(st.session_state['questionnaire_state']['questions_asked'])
        questions_skipped = len(st.session_state['questionnaire_state']['questions_skipped'])
        answered_correctly = len(st.session_state['questionnaire_state']['correct'])
        divide_by = questions_asked - questions_skipped or 1
        correct_prcnt = answered_correctly / divide_by * 100
        #st.title("Results:")
        st.markdown(f':grey[Asked: {questions_asked} | skipped: {questions_skipped} | correct: {answered_correctly} ({correct_prcnt}%)]')

     
    def generate_q_options(q_idx, question_with_options, q_idx_started_1):
        options = {}
        q_idx_str = str(q_idx_started_1)
        
        # Generate options for UI and 
        # "handlers" to disable all options on click and select only the clicked option
        for idx, option in enumerate(question_with_options['options'], start=1):
            idx_str = str(idx)
            q_key = f'q{q_idx_str}'
            options[idx_str] = st.checkbox(
                option, 
                key=f'{option}_{random.randint(0,1000)}', # we need unique checkboxes
                value = st.session_state.options_state[q_key][idx_str]['selected'], 
                on_change = mark_selected_disable_all_options, args=(q_idx, st.session_state['options_state'][q_key], idx_str,),
                disabled = st.session_state.options_state[q_key][idx_str]['disabled']
                )
        skip_option_key = f'skip_{q_key}'
        options[skip_option_key] = st.checkbox(
            f'Mark question #{q_idx_started_1} as invalid and skip it', 
            value = st.session_state.options_state[q_key][skip_option_key]['selected'], 
            on_change = mark_selected_disable_all_options, args=(q_idx, st.session_state['options_state'][q_key], skip_option_key,),  
            disabled = st.session_state.options_state[q_key][skip_option_key]['disabled']
            ) 
        
        # Logic to check if the option selected is correct, react and update score
        correct_option_idx_key = str(st.session_state['questions']['questions'][q_idx]['correct_option_index']+1)
        
        for key in options:
            value = options[key]
            response_status = 'wrong'
            if value:
                if key == skip_option_key:
                    response_status = 'skipped'
                    st.write(f'☠ Ok, the question #{q_idx+1} was skipped and will be ignored')
                elif key == correct_option_idx_key:
                    response_status = 'correct'
                    st.write('👍 Correct!')
                else:
                    response_status = 'wrong'
                    correct_option_idx = st.session_state['questions']['questions'][q_idx]['correct_option_index']
                    correct_option = st.session_state['questions']['questions'][q_idx]['options'][correct_option_idx]
                    st.markdown(f"😬 Unfortunately, no, the correct answer is *'{correct_option}'*")
                update_score(q_idx+1, response_status)
                show_stats()

    def render_question_title(q_idx):
        st.text("")
        st.subheader(f'''Q{q_idx+1}. {st.session_state['questions']['questions'][q_idx]['question']}''')
    
    for idx, _ in enumerate(st.session_state['questions']['questions']):
        render_question_title(idx)
        generate_q_options(idx, st.session_state['questions']['questions'][idx], idx+1)

def generate_questions():
    input = st.session_state['user_input']

    initialize_state(input)
    st.header('Questions:')
    renderQuestions()

def render_questions_btn_clicked(btn_clicked=False):
    st.session_state['render_questions_btn_clicked'] = btn_clicked
    

def clear_state():
    for key in st.session_state.keys():
        del st.session_state[key]

    
### Render UI and combine all together
st.title('Sarah PWC Quiz App')
st.write('Topic Based Quiz App')


# user_input = st.text_input("Enter a topic for your quiz")
num_questions = st.number_input("Enter the number of questions", min_value=1, max_value=10, value=5, key = 'num_question')

user_input = st.text_area(
    'Enter your topic', 
    'space',
    key='user_input',
    max_chars=50)

# Debug
# st.write(st.session_state)

st.button(
    'Generate questions', 
    key='render_questions_btn', 
    on_click=render_questions_btn_clicked, args=(True,)
    )

render_questions_btn_was_clicked = 'render_questions_btn_clicked' in st.session_state and st.session_state['render_questions_btn_clicked']
if render_questions_btn_was_clicked:
    generate_questions()