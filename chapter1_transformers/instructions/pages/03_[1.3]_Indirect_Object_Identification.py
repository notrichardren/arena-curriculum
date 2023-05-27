
import os, sys
from pathlib import Path
chapter = r"chapter1_transformers"
instructions_dir = Path(f"{os.getcwd().split(chapter)[0]}/{chapter}/instructions").resolve()
if str(instructions_dir) not in sys.path: sys.path.append(str(instructions_dir))
os.chdir(instructions_dir)

import streamlit as st
import st_dependencies

st_dependencies.styling()

import platform
is_local = (platform.processor() != "")

def section_0():

    st.sidebar.markdown(r"""

## Table of Contents

<ul class="contents">
    <li class='margtop'><a class='contents-el' href='#introduction'>Introduction</a></li>
    <li class='margtop'><a class='contents-el' href='#the-ioi-task'>The IOI task</a></li>
    <li class='margtop'><a class='contents-el' href='#have-some-sense-of-proportion'>Have some sense of proportion</a></li>
    <li class='margtop'><a class='contents-el' href='#keeping-track-of-your-guesses-predictions'>Keeping track of your guesses & predictions</a></li>
    <li class='margtop'><a class='contents-el' href='#content-learning-objectives'>Content & Learning Objectives</a></li>
    <li class='margtop'><a class='contents-el' href='#setup'>Setup</a></li>
</ul></li>""", unsafe_allow_html=True)

    st.markdown(r"""

 <img src="https://raw.githubusercontent.com/callummcdougall/TransformerLens-intro/main/images/page_images/leaves.png" width="350">


If you have any feedback on this course (e.g. bugs, confusing explanations, parts that you feel could be structured better), please let me know using [this Google Form](https://forms.gle/2ZhdHa87wWsrATjh9).


# Indirect Object Identification


## Introduction

This notebook / document is built around the [Interpretability in the Wild](https://arxiv.org/abs/2211.00593) paper, in which the authors aim to understand the **indirect object identification circuit** in GPT-2 small. This circuit is resposible for the model's ability to complete sentences like `"John and Mary went to the shops, John gave a bag to"` with the correct token "`" Mary"`.

It is loosely divided into different sections, each one with their own flavour. Sections 1, 2 & 3 are derived from Neel Nanda's notebook [Exploratory_Analysis_Demo](https://colab.research.google.com/github/neelnanda-io/TransformerLens/blob/main/activation_patching_in_TL_demo.py.ipynb#scrollTo=uw7PmPbLuzVO). The flavour of these exercises is experimental and loose, with a focus on demonstrating what exploratory analysis looks like in practice with the transformerlens library. They skimp on rigour, and instead try to speedrun the process of finding suggestive evidence for this circuit. The code and exercises are simple and generic, but accompanied with a lot of detail about what each stage is doing, and why (plus several optional details and tangents). Section 4 introduces you to the idea of **path patching**, which is a more rigorous and structured way of analysing the model's behaviour. Here, you'll be replicating some of the results of the paper, which will serve to rigorously validate the insights gained from earlier sections. It's the most technically dense of all five sections. Lastly, sections 5 & 6 are much less structured, and have a stronger focus on open-ended exercises & letting you go off and explore for yourself.

Which exercises you want to do will depend on what you're hoping to get out of these exercises. For example:

* You want to understand activation patching - **1, 2, 3**
* You want to get a sense of how to do exploratory analysis on a model - **1, 2, 3**
* You want to understand activation and path patching - **1, 2, 3, 4**
* You want to understand the IOI circuit fully, and replicate the paper's key results - **1, 2, 3, 4, 5**
* You want to understand the IOI circuit fully, and replicate the paper's key results (but you already understand activation patching) - **1, 2, 4, 5**
* You want to understand IOI, and then dive deeper e.g. by looking for more circuits in models or investigating anomalies - **1, 2, 3, 4, 5, 6**

*Note - if you find yourself getting frequent CUDA memory errors, you can periodically call `torch.cuda.empty_cache()` to [free up some memory](https://stackoverflow.com/questions/57858433/how-to-clear-gpu-memory-after-pytorch-model-training-without-restarting-kernel).*

Each exercise will have a difficulty and importance rating out of 5, as well as an estimated maximum time you should spend on these exercises and sometimes a short annotation. You should interpret the ratings & time estimates relatively (e.g. if you find yourself spending about 50% longer on the exercises than the time estimates, adjust accordingly). Please do skip exercises / look at solutions if you don't feel like they're important enough to be worth doing, and you'd rather get to the good stuff!


## The IOI task

The first step when trying to reverse engineer a circuit in a model is to identify *what* capability we want to reverse engineer. Indirect Object Identification is a task studied in Redwood Research's excellent [Interpretability in the Wild](https://arxiv.org/abs/2211.00593) paper (see [Neel Nanda's interview with the authors](https://www.youtube.com/watch?v=gzwj0jWbvbo) or [Kevin Wang's Twitter thread](https://threadreaderapp.com/thread/1587601532639494146.html) for an overview). The task is to complete sentences like "When Mary and John went to the store, John gave a drink to" with " Mary" rather than " John".

In the paper they rigorously reverse engineer a 26 head circuit, with 7 separate categories of heads used to perform this capability. The circuit they found roughly breaks down into three parts:

1. Identify what names are in the sentence
2. Identify which names are duplicated
3. Predict the name that is *not* duplicated

Why was this task chosen? The authors give a very good explanation for their choice in their [video walkthrough of their paper](https://www.youtube.com/watch?v=gzwj0jWbvbo), which you are encouraged to watch. To be brief, some of the reasons were:

* This is a fairly common grammatical structure, so we should expect the model to build some circuitry for solving it quite early on (after it's finished with all the more basic stuff, like n-grams, punctuation, induction, and simpler grammatical structures than this one).
* It's easy to measure: the model always puts a much higher probability on the IO and S tokens (i.e. `" Mary"` and `" John"`) than any others, and this is especially true once the model starts being stripped down to the core part of the circuit we're studying. So we can just take the logit difference between these two tokens, and use this as a metric for how well the model can solve the task.
* It is a crisp and well-defined task, so less likely to be solved in terms of memorisation of a large bag of heuristics (unlike e.g. tasks like "predict that the number `n+1` will follow `n`, which as Neel mentions in the video walkthrough is actually much more annoying and subtle than it first seems!).

A terminology note: `IO` will refer to the indirect object (in the example, `" Mary"`), `S1` and `S2` will refer to the two instances of the subject token (i.e. `" John"`), and `end` will refer to the end token `" to"` (because this is the position we take our prediction from, and we don't care about any tokens after this point). We will also sometimes use `S` to refer to the identity of the subject token (rather than referring to the first or second instance in particular).


## Have some sense of proportion

At a surface level, these exercises are designed to take you through the indirect object identification circuit. But it's also designed to make you a better interpretability researcher! As a result, most exercises will be doing a combination of:

1. Showing you some new characteristic of the circuit, and
2. Teaching you how to use tools and interpret results in a broader mech interp context.

Here is a rough conceptual graph showing all the different things you should be thinking about when going through these exercises, and how they relate to both of these goals, as well all the `transformerlens` tools which will help you.

<img src="https://raw.githubusercontent.com/callummcdougall/computational-thread-art/master/example_images/misc/ioi-map.png" width="900">

A key idea to have in mind during these exercises is the spectrum from simpler, more exploratory tools to more rigoruous, complex tools. On the far left, you have something like inspecting attention patterns, which can give a decent (but sometimes misleading) picture of what an attention head is doing. These should be some of the first tools you reach for, and you should be using them a lot even before you have concrete hypotheses about a circuit. On the far right, you have something like path patching, which is a pretty rigorous and effortful tool that is best used when you already have reasonably concrete hypotheses about a circuit. As we go through the exercises, we'll transition from left to right along this spectrum.


## Keeping track of your guesses & predictions

There's a lot to keep track of in these exercises as we work through them. You'll be exposed to new functions and modules from transformerlens, new ways to causally intervene in models, all the while building up your understanding of how the IOI task is performed. The notebook starts off exploratory in nature (lots of plotting and investigation), and gradually moves into more technical details, refined analysis, and replication of the paper's results, as we improve our understanding of the IOI circuit. You are recommended to keep a document or page of notes nearby as you go through these exercises, so you can keep track of the main takeaways from each section, as well as your hypotheses for how the model performs the task, and your ideas for how you might go off and test these hypotheses on your own if the notebook were to suddenly end.

If you are feeling extremely confused at any point, you can come back to the dropdown below, which contains diagrams explaining how the circuit works. There is also an accompanying intuitive explanation which you might find more helpful. However, I'd recommend you try and go through the notebook unassisted before looking at these.

<details>
<summary>Intuitive explanation of IOI circuit</summary>

First, let's start with an analogy for how transformers work (you can skip this if you've already read [my post](https://www.lesswrong.com/posts/euam65XjigaCJQkcN/an-analogy-for-understanding-transformers)). Imagine a line of people, who can only look forward. Each person has a token written on their chest, and their goal is to figure out what token the person in front of them is holding. Each person is allowed to pass a question backwards along the line (not forwards), and anyone can choose to reply to that question by passing information forwards to the person who asked. In this case, the sentence is `"When Mary and John went to the store, John gave a drink to Mary"`. You are the person holding the `" to"` token, and your goal is to figure out that the person in front of him has the `" Mary"` token.

To be clear about how this analogy relates to transformers:
* Each person in the line represents a vector in the residual stream. Initially they just store their own token, but they accrue more information as they ask questions and receive answers (i.e. as components write to the residual stream)
* The operation of an attention head is represented by a question & answer:
    * The person who asks is the destination token, the people who answer are the source tokens
    * The question is the query vector
    * The information *which determines who answers the question* is the key vector
    * The information *which gets passed back to the original asker* is the value vector

Now, here is how the IOI circuit works in this analogy. Each bullet point represents a class of attention heads.

* The person with the second `" John"` token asks the question "does anyone else hold the name `" John"`?". They get a reply from the first `" John"` token, who also gives him their location. So he now knows that `" John"` is repeated, and he knows that the first `" John"` token is 4th in the sequence.
    * These are *Duplicate Token Heads*
* You ask the question "which names are repeated?", and you get an answer from the person holding the second `" John"` token. You now also know that `" John"` is repeated, and where the first `" John"` token is. 
    * These are *S-Inhibition Heads*
* You ask the question "does anyone have a name that isn't `" John"`, and isn't at the 4th position in the sequence?". You get a reply from the person holding the `" Mary"` token, who tells you that they have name `" Mary"`. You use this as your prediction.
    * These are *Name Mover Heads*

This is a fine first-pass understanding of how the circuit works. A few other features:

* The person after the first `" John"` (holding `" went"`) had previously asked about the identity of the person behind him. So he knows that the 4th person in the sequence holds the `" John"` token, meaning he can also reply to the question of the person holding the second `" John"` token. *(previous token heads / induction heads)*
    * This might not seem necessary, but since previous token heads / induction heads are just a pretty useful thing to have in general, it makes sense that you'd want to make use of this information!
* If for some reason you forget to ask the question "does anyone have a name that isn't `" John"`, and isn't at the 4th position in the sequence?", then you'll have another chance to do this.
    * These are *(Backup Name Mover Heads)*
    * Their existance might be partly because transformers are trained with **dropout**. This can make them "forget" things, so it's important to have a backup method for recovering that information!
* You want to avoid overconfidence, so you also ask the question "does anyone have a name that isn't `" John"`, and isn't at the 4th position in the sequence?" another time, in order to ***anti-***predict the response that you get from this question. *(negative name mover heads)*
    * Yes, this is as weird as it sounds! The authors speculate that these heads "hedge" the predictions, avoiding high cross-entropy loss when making mistakes.

</details>

<details>
<summary>Diagram 1 (simple)</summary>

<img src="https://raw.githubusercontent.com/callummcdougall/computational-thread-art/master/example_images/misc/ioi-main-simple-a.png" width="1000">

</details>

<details>
<summary>Diagram 2 (complex)</summary>

<img src="https://raw.githubusercontent.com/callummcdougall/computational-thread-art/master/example_images/misc/ioi-main-full-d.png" width="1250">

</details>


## Content & Learning Objectives


#### 1️⃣ Model & Task Setup

> ##### Learning objectives
> 
> * Understand the IOI task, and why the authors chose to study it
> * Build functions to demonstrate the model's performance on this task

#### 2️⃣ Logit Attribution

> ##### Learning objectives
> 
> * Perform direct logit attribution to figure out which heads are writing to the residual stream in a significant way
> * Learn how to use different transformerlens helper functions, which decompose the residual stream in different ways

#### 3️⃣ Activation Patching

> ##### Learning objectives
> 
> * Understand the idea of activation patching, and how it can be used
>     * Implement some of the activation patching helper functinos in transformerlens from scratch (i.e. using hooks)
> * Use activation patching to track the layers & sequence positions in the residual stream where important information is stored and processed
> * By the end of this section, you should be able to draw a rough sketch of the IOI circuit

#### 4️⃣ Path Patching

> ##### Learning objectives
> 
> * Understand the idea of path patching, and how it differs from activation patching
> * Implement path patching from scratch (i.e. using hooks)
> * Replicate several of the results in the [IOI paper](https://arxiv.org/abs/2211.00593)

#### 5️⃣ Paper Replication

> ##### Learning objectives
> 
> * Replicate most of the other results from the [IOI paper](https://arxiv.org/abs/2211.00593)
> * Practice more open-ended, less guided coding

#### 6️⃣ Bonus / exploring anomalies

> ##### Learning objectives
> 
> * Explore other parts of the model (e.g. negative name mover heads, and induction heads)
> * Understand the subtleties present in model circuits, and the fact that there are often more parts to a circuit than seem obvious after initial investigation
> * Understand the importance of the three quantitative criteria used by the paper: **faithfulness**, **completeness** and **minimality**


## Setup


```python
import os; os.environ["ACCELERATE_DISABLE_RICH"] = "1"
import sys
from pathlib import Path
import torch as t
from torch import Tensor
import numpy as np
import einops
from tqdm.notebook import tqdm
import plotly.express as px
import webbrowser
import re
import itertools
from jaxtyping import Float, Int, Bool
from typing import List, Optional, Callable, Tuple, Dict, Literal, Set
from functools import partial
from IPython.display import display, HTML
from rich.table import Table, Column
from rich import print as rprint
import circuitsvis as cv
from pathlib import Path
from transformer_lens.hook_points import HookPoint
from transformer_lens import utils, HookedTransformer, ActivationCache
from transformer_lens.components import Embed, Unembed, LayerNorm, MLP

t.set_grad_enabled(False)

# Make sure exercises are in the path
chapter = r"chapter1_transformers"
exercises_dir = Path(f"{os.getcwd().split(chapter)[0]}/{chapter}/exercises").resolve()
section_dir = exercises_dir / "part3_indirect_object_identification"
if str(exercises_dir) not in sys.path: sys.path.append(str(exercises_dir))

from plotly_utils import imshow, line, scatter, bar
import part3_indirect_object_identification.tests as tests

device = t.device("cuda") if t.cuda.is_available() else t.device("cpu")

MAIN = __name__ == "__main__"

```



""", unsafe_allow_html=True)


def section_1():

    st.sidebar.markdown(r"""

## Table of Contents

<ul class="contents">
    <li class='margtop'><a class='contents-el' href='#loading-our-model'>Loading our model</a></li>
    <li class='margtop'><a class='contents-el' href='#exercise-implement-the-performance-evaluation-function'><b>Exercise</b> - implement the performance evaluation function</a></li>
    <li class='margtop'><a class='contents-el' href='#brainstorm-what's-actually-going-on'>Brainstorm What's Actually Going On</a></li>
</ul></li>""", unsafe_allow_html=True)

    st.markdown(r"""

# 1️⃣ Model & Task Setup


> ##### Learning objectives
> 
> * Understand the IOI task, and why the authors chose to study it
> * Build functions to demonstrate the model's performance on this task


## Loading our model


The first step is to load in our model, GPT-2 Small, a 12 layer and 80M parameter transformer with `HookedTransformer.from_pretrained`. The various flags are simplifications that preserve the model's output but simplify its internals.


```python

if MAIN:
    model = HookedTransformer.from_pretrained(
        "gpt2-small",
        center_unembed=True,
        center_writing_weights=True,
        fold_ln=True,
        refactor_factored_attn_matrices=True,
    )

```

<details>
<summary>Note on <code>refactor_factored_attn_matrices</code> (optional)</summary>

This argument means we redefine the matrices $W_Q$, $W_K$, $W_V$ and $W_O$ in the model (without changing the model's actual behaviour).

For example, we know that instead of working with $W_Q$ and $W_K$ individually, the only matrix we actually need to use in the model is the low-rank matrix $W_Q W_K^T$ (note that I'm using the convention of matrix multiplication on the right, which matches the code in transformerlens and previous exercises in this series, but doesn't match Anthropic's Mathematical Frameworks paper). So if we perform singular value decomposition $W_Q W_K^T = U S V^T$, then we see that we can just as easily define $W_Q = U \sqrt{S}$ and $W_K = $V \sqrt{S}$ and use these instead. This means that $W_Q$ and $W_K$ both have orthogonal columns with matching norms. You can investigate this yourself (e.g. using the code below). This is arguably a more interpretable setup, because now there's no obvious asymmetry between the keys and queries.

There's also some fiddlyness with how biases are handled in this factorisation, which is why the comments above don't hold absolutely (see the documnentation for more info).

```python
# Show column norms are the same (except first few, for fiddly bias reasons)
line([model.W_Q[0, 0].pow(2).sum(0), model.W_K[0, 0].pow(2).sum(0)])
# Show columns are orthogonal (except first few, again)
W_Q_dot_products = einops.einsum(
    model.W_Q[0, 0], model.W_Q[0, 0], "d_model d_head_1, d_model d_head_2 -> d_head_1 d_head_2"
)
imshow(W_Q_dot_products)
```

In a similar way, since $W_{OV} = W_V W_O = U S V^T$, we can define $W_V = U S$ and $W_O = V^T$. This is arguably a more interpretable setup, because now $W_O$ is just a rotation, and doesn't change the norm, so $z$ has the same norm as the result of the head.
</details>

<details>
<summary>Note on <code>fold_ln</code>, <code>center_unembed</code> and <code>center_writing_weights</code> (optional)</summary>

See link [here](https://github.com/neelnanda-io/TransformerLens/blob/main/further_comments.md#what-is-layernorm-folding-fold_ln) for comments.
</details>


The next step is to verify that the model can *actually* do the task! Here we use `utils.test_prompt`, and see that the model is significantly better at predicting Mary than John!

<details><summary>Asides</summary>

Note: If we were being careful, we'd want to run the model on a range of prompts and find the average performance. We'll do more stuff like this in the fourth section (when we try to replicate some of the paper's results, and take a more rigorous approach).

`prepend_bos` is a flag to add a BOS (beginning of sequence) to the start of the prompt. GPT-2 was not trained with this, but I find that it often makes model behaviour more stable, as the first token is treated weirdly.
</details>


```python
# Here is where we test on a single prompt
# Result: 70% probability on Mary, as we expect


if MAIN:
    example_prompt = "After John and Mary went to the store, John gave a bottle of milk to"
    example_answer = " Mary"
    utils.test_prompt(example_prompt, example_answer, model, prepend_bos=True)

```

We now want to find a reference prompt to run the model on. Even though our ultimate goal is to reverse engineer how this behaviour is done in general, often the best way to start out in mechanistic interpretability is by zooming in on a concrete example and understanding it in detail, and only *then* zooming out and verifying that our analysis generalises. In section 3, we'll work with a dataset similar to the one used by the paper authors, but this probably wouldn't be the first thing we reached for if we were just doing initial investigations.

We'll run the model on 4 instances of this task, each prompt given twice - one with the first name as the indirect object, one with the second name. To make our lives easier, we'll carefully choose prompts with single token names and the corresponding names in the same token positions.

<details><summary>Aside on tokenization</summary>

We want models that can take in arbitrary text, but models need to have a fixed vocabulary. So the solution is to define a vocabulary of **tokens** and to deterministically break up arbitrary text into tokens. Tokens are, essentially, subwords, and are determined by finding the most frequent substrings - this means that tokens vary a lot in length and frequency!

Tokens are a *massive* headache and are one of the most annoying things about reverse engineering language models... Different names will be different numbers of tokens, different prompts will have the relevant tokens at different positions, different prompts will have different total numbers of tokens, etc. Language models often devote significant amounts of parameters in early layers to convert inputs from tokens to a more sensible internal format (and do the reverse in later layers). You really, really want to avoid needing to think about tokenization wherever possible when doing exploratory analysis (though, of course, it's relevant later when trying to flesh out your analysis and make it rigorous!). HookedTransformer comes with several helper methods to deal with tokens: `to_tokens, to_string, to_str_tokens, to_single_token, get_token_position`

**Exercise:** I recommend using `model.to_str_tokens` to explore how the model tokenizes different strings. In particular, try adding or removing spaces at the start, or changing capitalization - these change tokenization!</details>


```python

if MAIN:
    prompt_format = [
        "When John and Mary went to the shops,{} gave the bag to",
        "When Tom and James went to the park,{} gave the ball to",
        "When Dan and Sid went to the shops,{} gave an apple to",
        "After Martin and Amy went to the park,{} gave a drink to",
    ]
    name_pairs = [
        (" Mary", " John"),
        (" Tom", " James"),
        (" Dan", " Sid"),
        (" Martin", " Amy"),
    ]
    
    # Define 8 prompts, in 4 groups of 2 (with adjacent prompts having answers swapped)
    prompts = [
        prompt.format(name) 
        for (prompt, names) in zip(prompt_format, name_pairs) for name in names[::-1] 
    ]
    # Define the answers for each prompt, in the form (correct, incorrect)
    answers = [names[::i] for names in name_pairs for i in (1, -1)]
    # Define the answer tokens (same shape as the answers)
    answer_tokens = t.concat([
        model.to_tokens(names, prepend_bos=False).T for names in answers
    ])
    
    rprint(prompts)
    rprint(answers)
    rprint(answer_tokens)

```

```python

if MAIN:
    table = Table("Prompt", "Correct", "Incorrect", title="Prompts & Answers:")
    
    for prompt, answer in zip(prompts, answers):
        table.add_row(prompt, repr(answer[0]), repr(answer[1]))
    
    rprint(table)

```

<details>
<summary>Aside - the <code>rich</code> library</summary>

The outputs above were created by `rich`, a fun library which prints things in nice formats. It has functions like `rich.table.Table`, which are very easy to use but can produce visually clear outputs which are sometimes useful.

You can also color the columns of a table, by using the `rich.table.Column` argument with the `style` parameter:

```python
cols = [
    "Prompt",
    Column("Correct", style="rgb(0,200,0) bold"),
    Column("Incorrect", style="rgb(255,0,0) bold"),
]
table = Table(*cols, title="Prompts & Answers:")

for prompt, answer in zip(prompts, answers):
    table.add_row(prompt, repr(answer[0]), repr(answer[1]))

rprint(table)
```
</details>


We now run the model on these prompts and use `run_with_cache` to get both the logits and a cache of all internal activations for later analysis.


```python

if MAIN:
    tokens = model.to_tokens(prompts, prepend_bos=True)
    # Move the tokens to the GPU
    tokens = tokens.to(device)
    # Run the model and cache all activations
    original_logits, cache = model.run_with_cache(tokens)

```

We'll later be evaluating how model performance differs upon performing various interventions, so it's useful to have a metric to measure model performance. Our metric here will be the **logit difference**, the difference in logit between the indirect object's name and the subject's name (eg, `logit(Mary) - logit(John)`).


## Exercise - implement the performance evaluation function

```c
Difficulty: 🟠🟠🟠⚪⚪
Importance: 🟠🟠🟠🟠⚪

You should spend up to 10-15 minutes on this exercise.

It's important to understand exactly what this function is computing, and why it matters.
```

This function should take in your model's logit output (shape `(batch, seq, d_vocab)`), and the array of answer tokens (shape `(batch, 2)`, containing the token ids of correct and incorrect answers respectively for each sequence), and return the logit difference as described above. If `per_prompt` is False, then it should take the mean over the batch dimension, if not then it should return an array of length `batch`.


```python
def logits_to_ave_logit_diff(
    logits: Float[Tensor, "batch seq d_vocab"],
    answer_tokens: Float[Tensor, "batch 2"] = answer_tokens,
    per_prompt: bool = False
):
    '''
    Returns logit difference between the correct and incorrect answer.

    If per_prompt=True, return the array of differences rather than the average.
    '''
    pass


```

<details>
<summary>Solution</summary>


```python
def logits_to_ave_logit_diff(
    logits: Float[Tensor, "batch seq d_vocab"],
    answer_tokens: Float[Tensor, "batch 2"] = answer_tokens,
    per_prompt: bool = False
):
    '''
    Returns logit difference between the correct and incorrect answer.

    If per_prompt=True, return the array of differences rather than the average.
    '''
    # SOLUTION
    # Only the final logits are relevant for the answer
    final_logits: Float[Tensor, "batch d_vocab"] = logits[:, -1, :]
    # Get the logits corresponding to the indirect object / subject tokens respectively
    answer_logits: Float[Tensor, "batch 2"] = final_logits.gather(dim=-1, index=answer_tokens)
    # Find logit difference
    correct_logits, incorrect_logits = answer_logits.unbind(dim=-1)
    answer_logit_diff = correct_logits - incorrect_logits
    return answer_logit_diff if per_prompt else answer_logit_diff.mean()


# tests.test_logits_to_ave_logit_diff(logits_to_ave_logit_diff)
```
</details>


```python

if MAIN:
    original_per_prompt_diff = logits_to_ave_logit_diff(original_logits, answer_tokens, per_prompt=True)
    print("Per prompt logit difference:", original_per_prompt_diff)
    original_average_logit_diff = logits_to_ave_logit_diff(original_logits, answer_tokens)
    print("Average logit difference:", original_average_logit_diff)

```

```python

if MAIN:
    cols = [
        "Prompt", 
        Column("Correct", style="rgb(0,200,0) bold"), 
        Column("Incorrect", style="rgb(255,0,0) bold"), 
        Column("Logit Difference", style="bold")
    ]
    table = Table(*cols, title="Logit differences")
    
    for prompt, answer, logit_diff in zip(prompts, answers, original_per_prompt_diff):
        table.add_row(prompt, repr(answer[0]), repr(answer[1]), f"{logit_diff.item():.3f}")
    
    rprint(table)

```

## Brainstorm What's Actually Going On



Before diving into running experiments, it's often useful to spend some time actually reasoning about how the behaviour in question could be implemented in the transformer. **This is optional, and you'll likely get the most out of engaging with this section if you have a decent understanding already of what a transformer is and how it works!**

You don't have to do this and forming hypotheses after exploration is also reasonable, but I think it's often easier to explore and interpret results with some grounding in what you might find. In this particular case, I'm cheating somewhat, since I know the answer, but I'm trying to simulate the process of reasoning about it!

Note that often your hypothesis will be wrong in some ways and often be completely off. We're doing science here, and the goal is to understand how the model *actually* works, and to form true beliefs! There are two separate traps here at two extremes that it's worth tracking:
* Confusion: Having no hypotheses at all, getting a lot of data and not knowing what to do with it, and just floundering around
* Dogmatism: Being overconfident in an incorrect hypothesis and being unwilling to let go of it when reality contradicts you, or flinching away from running the experiments that might disconfirm it.

**Exercise:** Spend some time thinking through how you might imagine this behaviour being implemented in a transformer. Try to think through this for yourself before reading through my thoughts!

<details> <summary>(*) <b>My reasoning</b></summary>

<h3>Brainstorming:</h3>

So, what's hard about the task? Let's focus on the concrete example of the first prompt, `"When John and Mary went to the shops, John gave the bag to" -> " Mary"`.

A good starting point is thinking though whether a tiny model could do this, e.g. a <a href="https://transformer-circuits.pub/2021/framework/index.html">1L Attn-Only model</a>. I'm pretty sure the answer is no! Attention is really good at the primitive operations of looking nearby, or copying information. I can believe a tiny model could figure out that at `to` it should look for names and predict that those names came next (e.g. the skip trigram " John...to -> John"). But it's much harder to tell how <i>many</i> of each previous name there are - attending to each copy of John will look exactly the same as attending to a single John token. So this will be pretty hard to figure out on the " to" token!

The natural place to break this symmetry is on the second `" John"` token - telling whether there is an earlier copy of the <i>current</i> token should be a much easier task. So I might expect there to be a head which detects duplicate tokens on the second `" John"` token, and then another head which moves that information from the second `" John` token to the `" to"` token.

The model then needs to learn to predict `" Mary"` and <i>not</i> `" John"`. I can see two natural ways to do this:
1. Detect all preceding names and move this information to " to" and then delete the any name corresponding to the duplicate token feature. This feels easier done with a non-linearity, since precisely cancelling out vectors is hard, so I'd imagine an MLP layer deletes the `" John"` direction of the residual stream.
2. Have a head which attends to all previous names, but where the duplicate token features <i>inhibit</i> it from attending to specific names. So this only attends to Mary. And then the output of this head maps to the logits.

<details>
<summary>Spoiler - which one of these two is correct</summary>

It's the second one.
</details>

<h3>Experiment Ideas</h3>

A test that could distinguish these two is to look at which components of the model add directly to the logits - if it's mostly attention heads which attend to `" Mary"` and to neither `" John"` it's probably hypothesis 2, if it's mostly MLPs it's probably hypothesis 1.

And we should be able to identify duplicate token heads by finding ones which attend from `" John"` to `" John"`, and whose outputs are then moved to the `" to"` token by V-Composition with another head (Spoiler: It's more complicated than that!)

Note that all of the above reasoning is very simplistic and could easily break in a real model! There'll be significant parts of the model that figure out whether to use this circuit at all (we don't want to inhibit duplicated names when, e.g. figuring out what goes at the start of the <i>next</i> sentence), and may be parts towards the end of the model that do "post-processing" just before the final output. But it's a good starting point for thinking about what's going on.

</details>




""", unsafe_allow_html=True)


def section_2():

    st.sidebar.markdown(r"""

## Table of Contents

<ul class="contents">
    <li class='margtop'><a class='contents-el' href='#direct-logit-attribution'>Direct Logit Attribution</a></li>
    <li><ul class="contents">
        <li><a class='contents-el' href='#background-and-motivation-of-the-logit-difference'>Background and motivation of the logit difference</a></li>
        <li><a class='contents-el' href='#logit-diff-directions'>Logit diff directions</a></li>
    </ul></li>
    <li class='margtop'><a class='contents-el' href='#logit-lens'>Logit Lens</a></li>
    <li><ul class="contents">
        <li><a class='contents-el' href='#exercise-implement-residual-stack-to-logit-diff'><b>Exercise</b> - implement <code>residual_stack_to_logit_diff</code></a></li>
    </ul></li>
    <li class='margtop'><a class='contents-el' href='#layer-attribution'>Layer Attribution</a></li>
    <li class='margtop'><a class='contents-el' href='#head-attribution'>Head Attribution</a></li>
    <li class='margtop'><a class='contents-el' href='#recap-of-useful-functions-from-this-section'>Recap of useful functions from this section</a></li>
    <li class='margtop'><a class='contents-el' href='#attention-analysis'>Attention Analysis</a></li>
</ul></li>""", unsafe_allow_html=True)

    st.markdown(r"""

# 2️⃣ Logit Attribution


> ##### Learning objectives
> 
> * Perform direct logit attribution to figure out which heads are writing to the residual stream in a significant way
> * Learn how to use different transformerlens helper functions, which decompose the residual stream in different ways


## Direct Logit Attribution


The easiest part of the model to understand is the output - this is what the model is trained to optimize, and so it can always be directly interpreted! Often the right approach to reverse engineering a circuit is to start at the end, understand how the model produces the right answer, and to then work backwards (you will have seen this if you went through the balanced bracket classifier task, and in fact if you did then this section will probably be quite familiar to you and you should feel free to just skim through it). The main technique used to do this is called **direct logit attribution**

**Background:** The central object of a transformer is the **residual stream**. This is the sum of the outputs of each layer and of the original token and positional embedding. Importantly, this means that any linear function of the residual stream can be perfectly decomposed into the contribution of each layer of the transformer. Further, each attention layer's output can be broken down into the sum of the output of each head (See [A Mathematical Framework for Transformer Circuits](https://transformer-circuits.pub/2021/framework/index.html) for details), and each MLP layer's output can be broken down into the sum of the output of each neuron (and a bias term for each layer).

The logits of a model are `logits=Unembed(LayerNorm(final_residual_stream))`. The Unembed is a linear map, and LayerNorm is approximately a linear map, so we can decompose the logits into the sum of the contributions of each component, and look at which components contribute the most to the logit of the correct token! This is called **direct logit attribution**. Here we look at the direct attribution to the logit difference!


### Background and motivation of the logit difference

Logit difference is actually a *really* nice and elegant metric and is a particularly nice aspect of the setup of Indirect Object Identification. In general, there are two natural ways to interpret the model's outputs: the output logits, or the output log probabilities (or probabilities).

The logits are much nicer and easier to understand, as noted above. However, the model is trained to optimize the cross-entropy loss (the average of log probability of the correct token). This means it does not directly optimize the logits, and indeed if the model adds an arbitrary constant to every logit, the log probabilities are unchanged.

But `log_probs == logits.log_softmax(dim=-1) == logits - logsumexp(logits)`, and so `log_probs(" Mary") - log_probs(" John") = logits(" Mary") - logits(" John")` - the ability to add an arbitrary constant cancels out!

<details>
<summary>Technical details (if this equivalence doesn't seem obvious to you)</summary>

Let $\underline{\textbf{x}}$ be the logits, $\underline{\textbf{L}}$ be the log probs, and $\underline{\textbf{p}}$ be the probs. Then we have the following relations:

$$
p_i = \operatorname{softmax}(\underline{\textbf{x}})_i = \frac{e^{x_i}}{\sum_{i=1}^n e^{x_i}}
$$

and:

$$
L_i = \log p_i
$$

Combining these, we get:

$$
L_i = \log \frac{e^{x_i}}{\sum_{i=1}^n e^{x_i}} = x_i - \log \sum_{i=1}^n e^{x_i}
$$

Notice that the sum term on the right hand side is the same for all $i$, so we get:

$$
L_i - L_j = x_i - x_j
$$

in other words, the logit diff $x_i - x_j$ is the same as the log prob diff. This motivates the choice of logit diff as our choice of metric (since the model is directly training to make the log prob of the correct token large, and all other log probs small).

</details>

Further, the metric helps us isolate the precise capability we care about - figuring out *which* name is the Indirect Object. There are many other components of the task - deciding whether to return an article (the) or pronoun (her) or name, realising that the sentence wants a person next at all, etc. By taking the logit difference we control for all of that.

Our metric is further refined, because each prompt is repeated twice, for each possible indirect object. This controls for irrelevant behaviour such as the model learning that John is a more frequent token than Mary (this actually happens! The final layernorm bias increases the John logit by 1 relative to the Mary logit). Another way to handle this would be to use a large enough dataset (with names randomly chosen) that this effect is averaged out, which is what we'll do in section 3.



<details> <summary>Ignoring LayerNorm</summary>

LayerNorm is an analogous normalization technique to BatchNorm (that's friendlier to massive parallelization) that transformers use. Every time a transformer layer reads information from the residual stream, it applies a LayerNorm to normalize the vector at each position (translating to set the mean to 0 and scaling to set the variance to 1) and then applying a learned vector of weights and biases to scale and translate the normalized vector. This is *almost* a linear map, apart from the scaling step, because that divides by the norm of the vector and the norm is not a linear function. (The `fold_ln` flag when loading a model factors out all the linear parts).

But if we fixed the scale factor, the LayerNorm would be fully linear. And the scale of the residual stream is a global property that's a function of *all* components of the stream, while in practice there is normally just a few directions relevant to any particular component, so in practice this is an acceptable approximation. So when doing direct logit attribution we use the `apply_ln` flag on the `cache` to apply the global layernorm scaling factor to each constant. See [my clean GPT-2 implementation](https://colab.research.google.com/github/neelnanda-io/TransformerLens/blob/clean-transformer-demo/Clean_Transformer_Demo.ipynb#scrollTo=Clean_Transformer_Implementation) for more on LayerNorm.
</details>


### Logit diff directions


***Getting an output logit is equivalent to projecting onto a direction in the residual stream, and the same is true for getting the logit diff.***

<details>
<summary>If it's not clear what is meant by this statement, read this dropdown.</summary>

Suppose our final value in the residual stream for a single sequence and a position within that sequence is $x$ (i.e. $x$ is a vector of length $d_{model}$). Then (ignoring layernorm - see the point above for why it's okay to do this), we get logits by multiplying by the unembedding matrix $W_U$ (which has shape $(d_{model}, d_{vocab})$):

$$
\text{output} = x^T W_U
$$

Now, remember that we want the logit diff, which is $output_{IO} - output_{S}$ (the difference between the logits for our indirect object and subject). We can write this as:

$$
\text{logit diff} = (x^T W_U)_{IO} - (x^T W_U)_{S} = x^T (u_{IO} - u_{S})
$$

where $u_{IO}$ and $u_S$ are the columns of the unembedding matrix $W_U$ corresponding to the indirect object and subject tokens respectively.

To summarize, we've written the logit diff as a dot product between the vector in the residual stream and a constant vector (which is a function of the model's unembedding matrix). We call this vector $u_{IO} - u_{S}$ the **logit difference direction** (because it "points in the direction of largest logit difference"). To put it another way, if $x$ is a vector of fixed magnitude, then it maximises the logit difference when it is pointing in the same direction as the vector $u_{IO} - u_{S}$. We use the term "projection" synonymously with "dot product" here.

(If you've completed the exercise where we interpret a transformer on balanced / unbalanced bracket strings, this is basically the same principle. The only difference here is that we actually have a much larger unembedding vocabulary than just the classifications `{balanced, unbalanced}`, but since we're only interested in comparing the model's prediction for IO vs S, and the logits for these two tokens are usually larger than most others, this method is still well-justified).
</details>


We use `model.tokens_to_residual_directions` to map the answer tokens to that direction, and then convert this to a logit difference direction for each batch


```python

if MAIN:
    answer_residual_directions: Float[Tensor, "batch 2 d_model"] = model.tokens_to_residual_directions(answer_tokens)
    print("Answer residual directions shape:", answer_residual_directions.shape)
    
    correct_residual_directions, incorrect_residual_directions = answer_residual_directions.unbind(dim=1)
    logit_diff_directions: Float[Tensor, "batch d_model"] = correct_residual_directions - incorrect_residual_directions
    print(f"Logit difference directions shape:", logit_diff_directions.shape)

```

<details>
<summary>Aside - type annotations</summary>

If you haven't seen type annotations being used in this way, I'd encourage it, because they're pretty handy! You can keep track of tensor sizes without worrying about re-printing everything (this is especially useful if you're working in a python file in VSCode rather than a notebook, since in a notebook it's fine to just leave cell output there as a reference). It's also handy for your typechecker, if you're using VSCode.

Also note the use of `jaxtyping`, this is a better-maintained and [improved](https://github.com/nerfstudio-project/nerfstudio/issues/1171) version of the `tensortyping` library but works in basically the same way - you can see their documentation page [here](https://github.com/google/jaxtyping).
</details>

To verify that this works, we can apply this to the final residual stream for our cached prompts (after applying LayerNorm scaling) and verify that we get the same answer.

<details> <summary>Technical details</summary>

`logits = Unembed(LayerNorm(final_residual_stream))`, so we technically need to account for the centering, and then learned translation and scaling of the layernorm, not just the variance 1 scaling.

The centering is accounted for with the preprocessing flag `center_writing_weights` which ensures that every weight matrix writing to the residual stream has mean zero.

The learned scaling is folded into the unembedding weights `model.unembed.W_U` via `W_U_fold = layer_norm.weights[:, None] * unembed.W_U`

The learned translation is folded to `model.unembed.b_U`, a bias added to the logits (note that GPT-2 is not trained with an existing `b_U`). This roughly represents unigram statistics. But we can ignore this because each prompt occurs twice with names in the opposite order, so this perfectly cancels out.

Note that rather than using layernorm scaling we could just study cache["ln_final.hook_normalised"]

</details>


The code below does the following:

* Gets the final residual stream values from the `cache` object (which you should already have defined above).
* Apply layernorm scaling to these values.
    * This is done by `cache.apply_to_ln_stack`, a helpful function which takes a stack of residual stream values (e.g. a batch, or the residual stream decomposed into components), treats them as the input to a specific layer, and applies the layer norm scaling of that layer to them.
    * The keyword arguments here indicate that our input is the residual stream values for the last sequence position, and we want to apply the final layernorm in the model.
* Project them along the unembedding directions (you've already defined these above, as `logit_diff_directions`).


```python
# cache syntax - resid_post is the residual stream at the end of the layer, -1 gets the final layer. The general syntax is [activation_name, layer_index, sub_layer_type]. 

if MAIN:
    final_residual_stream: Float[Tensor, "batch seq d_model"] = cache["resid_post", -1]
    print(f"Final residual stream shape: {final_residual_stream.shape}")
    final_token_residual_stream: Float[Tensor, "batch d_model"] = final_residual_stream[:, -1, :]
    
    # Apply LayerNorm scaling (to just the final sequence position)
    # pos_slice is the subset of the positions we take - here the final token of each prompt
    scaled_final_token_residual_stream = cache.apply_ln_to_stack(final_token_residual_stream, layer=-1, pos_slice=-1)
    
    average_logit_diff = einops.einsum(
        scaled_final_token_residual_stream, logit_diff_directions,
        "batch d_model, batch d_model ->"
    ) / len(prompts)
    
    print(f"Calculated average logit diff: {average_logit_diff:.10f}")
    print(f"Original logit difference:     {original_average_logit_diff:.10f}")
    
    t.testing.assert_close(average_logit_diff, original_average_logit_diff)

```

## Logit Lens


We can now decompose the residual stream! First we apply a technique called the [**logit lens**](https://www.alignmentforum.org/posts/AcKRB8wDpdaN6v6ru/interpreting-gpt-the-logit-lens) - this looks at the residual stream after each layer and calculates the logit difference from that. This simulates what happens if we delete all subsequence layers.


### Exercise - implement `residual_stack_to_logit_diff`

```c
Difficulty: 🟠🟠🟠⚪⚪
Importance: 🟠🟠🟠⚪⚪

You should spend up to 10-15 minutes on this exercise.

Again, make sure you understand what the output of this function represents.
```

This function should look a lot like your code immediately above. `residual_stack` is a tensor of shape `(..., batch, d_model)` containing the residual stream values for the final sequence position. You should apply the final layernorm to these values, then project them in the logit difference directions.


```python
def residual_stack_to_logit_diff(
    residual_stack: Float[Tensor, "... batch d_model"], 
    cache: ActivationCache,
    logit_diff_directions: Float[Tensor, "batch d_model"] = logit_diff_directions,
) -> Float[Tensor, "..."]:
    '''
    Gets the avg logit difference between the correct and incorrect answer for a given 
    stack of components in the residual stream.
    '''
    pass


if MAIN:
    t.testing.assert_close(
        residual_stack_to_logit_diff(final_token_residual_stream, cache),
        original_average_logit_diff
    )

```

Once you have the solution, you can plot your results.

<details> <summary>Details on <code>accumulated_resid</code></summary>

Key for the plot below: `n_pre` means the residual stream at the start of layer n, `n_mid` means the residual stream after the attention part of layer n (`n_post` is the same as `n+1_pre` so is not included)

* `layer` is the layer for which we input the residual stream (this is used to identify *which* layer norm scaling factor we want)
* `incl_mid` is whether to include the residual stream in the middle of a layer, ie after attention & before MLP
* `pos_slice` is the subset of the positions used. See `utils.Slice` for details on the syntax.
* `return_labels` is whether to return the labels for each component returned (useful for plotting)
</details>


```python

if MAIN:
    accumulated_residual, labels = cache.accumulated_resid(layer=-1, incl_mid=True, pos_slice=-1, return_labels=True)
    # accumulated_residual has shape (component, batch, d_model)
    
    logit_lens_logit_diffs: Float[Tensor, "component"] = residual_stack_to_logit_diff(accumulated_residual, cache)
    
    line(
        logit_lens_logit_diffs, 
        hovermode="x unified",
        title="Logit Difference From Accumulated Residual Stream",
        labels={"x": "Layer", "y": "Logit Diff"},
        xaxis_tickvals=labels,
        width=800
    )

```

<details>
<summary>Question - what is the interpretation of this plot? What does this tell you about how the model solves this task?</summary>

Fascinatingly, we see that the model is utterly unable to do the task until layer 7, almost all performance comes from attention layer 9, and performance actually *decreases* from there.

This tells us that there must be something going on (primarily in layers 7, 8 and 9) which writes to the residual stream in the correct way to solve the IOI task. This allows us to narrow in our focus, and start asking questions about what kind of computation is going on in those layers (e.g. the contribution of attention layers vs MLPs, and which attention heads are most important).
</details>


## Layer Attribution


We can repeat the above analysis but for each layer (this is equivalent to the differences between adjacent residual streams)

Note: Annoying terminology overload - layer k of a transformer means the kth **transformer block**, but each block consists of an **attention layer** (to move information around) *and* an **MLP layer** (to process information).


```python

if MAIN:
    per_layer_residual, labels = cache.decompose_resid(layer=-1, pos_slice=-1, return_labels=True)
    per_layer_logit_diffs = residual_stack_to_logit_diff(per_layer_residual, cache)
    
    line(
        per_layer_logit_diffs, 
        hovermode="x unified",
        title="Logit Difference From Each Layer",
        labels={"x": "Layer", "y": "Logit Diff"},
        xaxis_tickvals=labels,
        width=800
    )

```

<details>
<summary>Question - what is the interpretation of this plot? What does this tell you about how the model solves this task?</summary>

We see that only attention layers matter, which makes sense! The IOI task is about moving information around (i.e. moving the correct name and not the incorrect name), and less about processing it. And again we note that attention layer 9 improves things a lot, while attention 10 and attention 11 *decrease* performance.
</details>


## Head Attribution


We can further break down the output of each attention layer into the sum of the outputs of each attention head. Each attention layer consists of 12 heads, which each act independently and additively.

<details> <summary>Decomposing attention output into sums of heads</summary>

The standard way to compute the output of an attention layer is by concatenating the mixed values of each head, and multiplying by a big output weight matrix. But as described in [A Mathematical Framework](https://transformer-circuits.pub/2021/framework/index.html) this is equivalent to splitting the output weight matrix into a per-head output (here `model.blocks[k].attn.W_O`) and adding them up (including an overall bias term for the entire layer).
</details>


```python

if MAIN:
    per_head_residual, labels = cache.stack_head_results(layer=-1, pos_slice=-1, return_labels=True)
    per_head_residual = einops.rearrange(
        per_head_residual, 
        "(layer head) ... -> layer head ...", 
        layer=model.cfg.n_layers
    )
    per_head_logit_diffs = residual_stack_to_logit_diff(per_head_residual, cache)
    
    imshow(
        per_head_logit_diffs, 
        labels={"x":"Head", "y":"Layer"}, 
        title="Logit Difference From Each Head",
        width=600
    )

```

We see that only a few heads really matter - heads 9.6 and 9.9 contribute a lot positively (explaining why attention layer 9 is so important), while heads 10.7 and 11.10 contribute a lot negatively (explaining why attention layer 10 and layer 11 are actively harmful). These correspond to (some of) the name movers and negative name movers discussed in the paper. There are also several heads that matter positively or negatively but less strongly (other name movers and backu name movers)

There are a few meta observations worth making here - our model has 144 heads, yet we could localise this behaviour to a handful of specific heads, using straightforward, general techniques. This supports the claim in [A Mathematical Framework](https://transformer-circuits.pub/2021/framework/index.html) that attention heads are the right level of abstraction to understand attention. It also really surprising that there are *negative* heads - eg 10.7 makes the incorrect logit 7x *more* likely. I'm not sure what's going on there, though the paper discusses some possibilities.


## Recap of useful functions from this section

Here, we take stock of all the functions from transformerlens which you might not have seen previously.

* `cache.apply_ln_to_stack`
    * Apply layernorm scaling to a stack of residual stream values.
    * We used this to help us go from "final value in residual stream" to "projection of logits in logit difference directions", without getting the code too messy!
* `cache.accumulated_resid(layer=None)`
    * Returns the accumulated residual stream up to layer `layer` (or up to the final value of residual stream if layer is None), i.e. a stack of previous residual streams up to that layer's input.
    * Useful when studying the **logit lens**.
    * First dimension of output is `(0_pre, 0_mid, 1_pre, 1_mid, ..., final_post)`
* `cache.decompose_resid(layer)`.
    * Decomposes the residual stream input to layer `layer` into a stack of the output of previous layers. The sum of these is the input to layer `layer`.
    * First dimension of output is `(embed, pos_embed, 0_attn_out, 0_mlp_out, ...)`.
* `cache.stack_head_results(layer)`
    * Returns a stack of all head results (i.e. residual stream contribution) up to layer `layer`
    * (i.e. like `decompose_resid` except it splits each attention layer by head rather than splitting each layer by attention/MLP)
    * First dimension of output is `layer * head` (we needed to rearrange to `(layer, head)` to plot it).


## Attention Analysis

Attention heads are particularly fruitful to study because we can look directly at their attention patterns and study from what positions they move information from and to. This is particularly useful here as we're looking at the direct effect on the logits so we need only look at the attention patterns from the final token.

We use the `circuitsvis` library (developed from Anthropic's PySvelte library) to visualize the attention patterns! We visualize the top 3 positive and negative heads by direct logit attribution, and show these for the first prompt (as an illustration).

<details> <summary>Interpreting Attention Patterns</summary>

A common mistake to make when looking at attention patterns is thinking that they must convey information about the *token* looked at (maybe accounting for the context of the token). But actually, all we can confidently say is that it moves information from the *residual stream position* corresponding to that input token. Especially later on in the model, there may be components in the residual stream that are nothing to do with the input token! Eg the period at the end of a sentence may contain summary information for that sentence, and the head may solely move that, rather than caring about whether it ends in ".", "!" or "?"
</details>


```python
def topk_of_Nd_tensor(tensor: Float[Tensor, "rows cols"], k: int):
    '''
    Helper function: does same as tensor.topk(k).indices, but works over 2D tensors.
    Returns a list of indices, i.e. shape [k, tensor.ndim].

    Example: if tensor is 2D array of values for each head in each layer, this will
    return a list of heads.
    '''
    i = t.topk(tensor.flatten(), k).indices
    return np.array(np.unravel_index(utils.to_numpy(i), tensor.shape)).T.tolist()



if MAIN:
    k = 3
    
    for head_type in ["Positive", "Negative"]:
    
        # Get the heads with largest (or smallest) contribution to the logit difference
        top_heads = topk_of_Nd_tensor(per_head_logit_diffs * (1 if head_type=="Positive" else -1), k)
    
        # Get all their attention patterns
    attn_patterns_for_important_heads: Float[Tensor, "head q k"] = t.stack([
        cache["pattern", layer][:, head].mean(0)
         for layer, head in top_heads
    ])

    # Display results
    display(HTML(f"<h2>Top {k} {head_type} Logit Attribution Heads</h2>"))
    display(cv.attention.attention_patterns(
        attention = attn_patterns_for_important_heads,
        tokens = model.to_str_tokens(tokens[0]),
        attention_head_names = [f"{layer}.{head}" for layer, head in top_heads],
    ))

```

Reminder - you can use `attention_patterns` or `attention_heads` for these visuals. The former lets you see the actual values, the latter lets you hover over tokens in a printed sentence (and it provides other useful features like locking on tokens, or a superposition of all heads in the display). Both can be useful in different contexts (although I'd recommend usually using `attention_patterns`, it's more useful in most cases for quickly getting a sense of attention patterns).

Try replacing `attention_patterns` above with `attention_heads`, and compare the output.

<details>
<summary>Help - my <code>attention_heads</code> plots are behaving weirdly.</summary>

This seems to be a bug in `circuitsvis` - on VSCode, the attention head plots continually shrink in size.

Until this is fixed, one way to get around it is to open the plots in your browser. You can do this inline with the `webbrowser` library:

```python
attn_heads = cv.attention.attention_heads(
    attention = attn_patterns_for_important_heads,
    tokens = model.to_str_tokens(tokens[0]),
    attention_head_names = [f"{layer}.{head}" for layer, head in top_heads],
)

path = "attn_heads.html"

with open(path, "w") as f:
    f.write(str(attn_heads))

webbrowser.open(path)
```

To check exactly where this is getting saved, you can print your current working directory with `os.getcwd()`.
</details>

From these plots, you might want to start thinking about the algorithm which is being implemented. In particular, for the attention heads with high positive attribution scores, where is `" to"` attending to? How might this head be affecting the logit diff score?

We'll save a full hypothesis for how the model works until the end of the next section.




""", unsafe_allow_html=True)


def section_3():

    st.sidebar.markdown(r"""

## Table of Contents

<ul class="contents">
    <li class='margtop'><a class='contents-el' href='#introduction'>Introduction</a></li>
    <li class='margtop'><a class='contents-el' href='#creating-a-metric'>Creating a metric</a></li>
    <li><ul class="contents">
        <li><a class='contents-el' href='#exercise-create-a-metric'><b>Exercise</b> - create a metric</a></li>
    </ul></li>
    <li class='margtop'><a class='contents-el' href='#residual-stream-patching'>Residual Stream Patching</a></li>
    <li><ul class="contents">
        <li><a class='contents-el' href='#exercise-implement-head-to-residual-patching'><b>Exercise</b> - implement head-to-residual patching</a></li>
    </ul></li>
    <li class='margtop'><a class='contents-el' href='#patching-in-residual-stream-by-block'>Patching in residual stream by block</a></li>
    <li><ul class="contents">
        <li><a class='contents-el' href='#exercise-optional-implement-head-to-block-patching'><b>Exercise</b> (optional) - implement head-to-block patching</a></li>
    </ul></li>
    <li class='margtop'><a class='contents-el' href='#head-patching'>Head Patching</a></li>
    <li><ul class="contents">
        <li><a class='contents-el' href='#exercise-implement-head-to-head-patching'><b>Exercise</b> - implement head-to-head patching</a></li>
    </ul></li>
    <li class='margtop'><a class='contents-el' href='#decomposing-heads'>Decomposing Heads</a></li>
    <li><ul class="contents">
        <li><a class='contents-el' href='#exercise-optional-implement-head-to-head-input-patching'><b>Exercise</b> (optional) - implement head-to-head-input patching</a></li>
    </ul></li>
    <li class='margtop'><a class='contents-el' href='#consolidating-understanding'>Consolidating Understanding</a></li>
</ul></li>""", unsafe_allow_html=True)

    st.markdown(r"""

# 3️⃣ Activation Patching


> ##### Learning objectives
> 
> * Understand the idea of activation patching, and how it can be used
>     * Implement some of the activation patching helper functinos in transformerlens from scratch (i.e. using hooks)
> * Use activation patching to track the layers & sequence positions in the residual stream where important information is stored and processed
> * By the end of this section, you should be able to draw a rough sketch of the IOI circuit


## Introduction


The obvious limitation to the techniques used above is that they only look at the very end of the circuit - the parts that directly affect the logits. Clearly this is not sufficient to understand the circuit! We want to understand how things compose together to produce this final output, and ideally to produce an end-to-end circuit fully explaining this behaviour.

The technique we'll use to investigate this is called **activation patching**. This was first introduced in [David Bau and Kevin Meng's excellent ROME paper](https://rome.baulab.info/), there called causal tracing.

The setup of activation patching is to take two runs of the model on two different inputs, the clean run and the corrupted run. The clean run outputs the correct answer and the corrupted run does not. The key idea is that we give the model the corrupted input, but then **intervene** on a specific activation and **patch** in the corresponding activation from the clean run (ie replace the corrupted activation with the clean activation), and then continue the run. And we then measure how much the output has updated towards the correct answer.

We can then iterate over many possible activations and look at how much they affect the corrupted run. If patching in an activation significantly increases the probability of the correct answer, this allows us to *localise* which activations matter.

The ability to localise is a key move in mechanistic interpretability - if the computation is diffuse and spread across the entire model, it is likely much harder to form a clean mechanistic story for what's going on. But if we can identify precisely which parts of the model matter, we can then zoom in and determine what they represent and how they connect up with each other, and ultimately reverse engineer the underlying circuit that they represent.


The diagrams below demonstrate activation patching on an abstract neural network (the nodes represent activations, and the arrows between them are weight connections).

A regular forward pass on the clean input looks like:

<img src="https://raw.githubusercontent.com/callummcdougall/computational-thread-art/master/example_images/misc/simpler-patching-1c.png" width="300">

And activation patching from a corrupted input (green) into a forward pass for the clean input (black) looks like:

<img src="https://raw.githubusercontent.com/callummcdougall/computational-thread-art/master/example_images/misc/simpler-patching-2c.png" width="440">

where the dotted line represents patching in a value (i.e. during the forward pass on the clean input, we replace node $D$ with the value it takes on the corrupted input). Nodes $H$, $G$ and $F$ are colored orange, to represent that they now follow a distribution which is not the same as clean or corrupted.


We can patch into a transformer in many different ways (e.g. values of the residual stream, the MLP, or attention heads' output - see below). We can also get even more granular by patching at particular sequence positions (not shown in diagram).

<img src="https://raw.githubusercontent.com/callummcdougall/computational-thread-art/master/example_images/misc/simpler-patching-examples.png" width="840">


The above was all fairly abstract, so let's zoom in and lay out a concrete example to understand Indirect Object Identification.

Here our clean input will be the original sentences (e.g. <code>"When Mary and John went to the store, John gave a drink to"</code>) and our corrupted input will have the subject token flipped (e.g. <code>"When Mary and John went to the store, <u>Mary</u> gave a drink to"</code>). Patching from the corrupted input to the clean input is a causal intervention which will allow us to understand precisely which parts of the network are identifying the indirect object. If a component is important, then patching into that component will reverse the signal that this component produces, hence making performance much worse. 


Question - we could instead have our corrupted sentence be <code>"When <u>John</u> and <u>Mary</u> went to the store, <u>Mary</u> gave a drink to"</code> (i.e. flip all 3 occurrences of names in the sentence). Why do you think we don't do this?

<details>
<summary>Hint</summary>

What if, at some point during the model's forward pass on the prompt `"When Mary and John went to the store, John gave a drink to"`, it contains some representation of the information **"the indirect object is the fourth token in this sequence"**?
</details>

<details>
<summary>Answer</summary>

The model could point to the indirect object `' Mary'` in two different ways:

* Via **token information**, i.e. **"the indirect object is the token `' Mary'`"**.
* Via **positional information**, i.e. **"the indirect object is the fourth token in this sequence"**.

We want the corrupted dataset to reverse both these signals when it's patched into the clean dataset. But if we corrupted the dataset by flipping all three names, then:

* The token information is flipped, because the corresponding information in the model for the corrupted prompt will be **"the indirect object is the token `' Mary'`"**.
* The positional information is ***not*** flipped, because the corresponding information will still be **"the indirect object is the fourth token in this sequence"**.

In fact, in the bonus section we'll take advantage of this fact to try and disentangle whether token or positional information is being used by the model (i.e. by flipping the token information but not the positional information, and vice-versa). Spoiler alert - it turns out to be using a bit of both!
</details>


One natural thing to patch in is the residual stream at a specific layer and specific position. For example, the model is likely intitially doing some processing on the `S2` token to realise that it's a duplicate, but then uses attention to move that information to the `end` token. So patching in the residual stream at the `end` token will likely matter a lot in later layers but not at all in early layers.

We can zoom in much further and patch in specific activations from specific layers. For example, we think that the output of head 9.9 on the final token is significant for directly connecting to the logits, so we predict that just patching the output of this head will significantly affect performance.

Note that this technique does *not* tell us how the components of the circuit connect up, just what they are.


TransformerLens has helpful built-in functions to perform activation patching, but in order to understand the process better, you're now going to implement some of these functions from first principles (i.e. just using hooks). You'll be able to test your functions by comparing their output to the built-in functions. 

If you need a refresher on hooks, you can return to the exercises on induction heads (which take you through how to use hooks, as well as how to cache activations).


```python
from transformer_lens import patching

```

## Creating a metric


Before we patch, we need to create a metric for evaluating a set of logits. Since we'll be running our **corrupted prompts** (with `S2` replaced with the wrong name) and patching in our **clean prompts**, it makes sense to choose a metric such that:

* A value of zero means no change (from the performance on the corrupted prompt)
* A value of one means clean performance has been completely recovered

For example, if we patched in the entire clean prompt, we'd get a value of one. If our patching actually makes the model even better at solving the task than its regular behaviour on the clean prompt then we'd get a value greater than 1, but generally we expect values between 0 and 1.

It also makes sense to have the metric be a linear function of the logit difference. This is enough to uniquely specify a metric.


```python

if MAIN:
    clean_tokens = tokens
    # Swap each adjacent pair to get corrupted tokens
    indices = [i+1 if i % 2 == 0 else i-1 for i in range(len(tokens))]
    corrupted_tokens = clean_tokens[indices]
    
    print(
        "Clean string 0:    ", model.to_string(clean_tokens[0]), "\n"
        "Corrupted string 0:", model.to_string(corrupted_tokens[0])
    )

```

```python

if MAIN:
    clean_logits, clean_cache = model.run_with_cache(clean_tokens)
    corrupted_logits, corrupted_cache = model.run_with_cache(corrupted_tokens)
    
    clean_logit_diff = logits_to_ave_logit_diff(clean_logits, answer_tokens)
    print(f"Clean logit diff: {clean_logit_diff:.4f}")
    
    corrupted_logit_diff = logits_to_ave_logit_diff(corrupted_logits, answer_tokens)
    print(f"Corrupted logit diff: {corrupted_logit_diff:.4f}")

```

### Exercise - create a metric

```c
Difficulty: 🟠🟠⚪⚪⚪
Importance: 🟠🟠🟠⚪⚪

You should spend up to ~10 minutes on this exercise.
```

Fill in the function `ioi_metric` below, to create the required metric. Note that we can afford to use default arguments in this function, because we'll be using the same dataset for this whole section.

**Important note** - this function needs to return a scalar tensor, rather than a float. If not, then some of the patching functions later on won't work. The type signature of this is `Float[Tensor, ""]`.


```python

if MAIN:
    def ioi_metric(
        logits: Float[Tensor, "batch seq d_vocab"], 
        answer_tokens: Float[Tensor, "batch 2"] = answer_tokens,
        corrupted_logit_diff: float = corrupted_logit_diff,
        clean_logit_diff: float = clean_logit_diff,
    ) -> Float[Tensor, ""]:
        '''
        Linear function of logit diff, calibrated so that it equals 0 when performance is 
        same as on corrupted input, and 1 when performance is same as on clean input.
        '''
    pass

    t.testing.assert_close(ioi_metric(clean_logits).item(), 1.0)
    t.testing.assert_close(ioi_metric(corrupted_logits).item(), 0.0)
    t.testing.assert_close(ioi_metric((clean_logits + corrupted_logits) / 2).item(), 0.5)

```

<details>
<summary>Solution</summary>


```python
def residual_stack_to_logit_diff(
    residual_stack: Float[Tensor, "... batch d_model"], 
    cache: ActivationCache,
    logit_diff_directions: Float[Tensor, "batch d_model"] = logit_diff_directions,
) -> Float[Tensor, "..."]:
    '''
    Gets the avg logit difference between the correct and incorrect answer for a given 
    stack of components in the residual stream.
    '''
    # SOLUTION
    batch_size = residual_stack.size(-2)
    scaled_residual_stack = cache.apply_ln_to_stack(residual_stack, layer=-1, pos_slice=-1)
    return einops.einsum(
        scaled_residual_stack, logit_diff_directions,
        "... batch d_model, batch d_model -> ..."
    ) / batch_size


# Test function by checking that it gives the same result as the original logit difference

def topk_of_Nd_tensor(tensor: Float[Tensor, "rows cols"], k: int):
    '''
    Helper function: does same as tensor.topk(k).indices, but works over 2D tensors.
    Returns a list of indices, i.e. shape [k, tensor.ndim].

    Example: if tensor is 2D array of values for each head in each layer, this will
    return a list of heads.
    '''
    i = t.topk(tensor.flatten(), k).indices
    return np.array(np.unravel_index(utils.to_numpy(i), tensor.shape)).T.tolist()


    # SOLUTION
```
</details>


## Residual Stream Patching


Lets begin with a simple example: we patch in the residual stream at the start of each layer and for each token position. Before you write your own function to do this, let's see what this looks like with TransformerLens' `patching` module. Run the code below.


```python

if MAIN:
    act_patch_resid_pre = patching.get_act_patch_resid_pre(
        model = model,
        corrupted_tokens = corrupted_tokens,
        clean_cache = clean_cache,
        patching_metric = ioi_metric
    )
    
    labels = [f"{tok} {i}" for i, tok in enumerate(model.to_str_tokens(clean_tokens[0]))]

```

```python

if MAIN:
    imshow(
        act_patch_resid_pre, 
        labels={"x": "Position", "y": "Layer"},
        x=labels,
        title="resid_pre Activation Patching",
        width=600
    )

```

Question - what is the interpretation of this graph? What significant things does it tell you about the nature of how the model solves this task?

<details>
<summary>Hint</summary>

Think about locality of computation.
</details>

<details>
<summary>Answer</summary>

Originally all relevant computation happens on `S2`, and at layers 7 and 8, the information is moved to `END`. Moving the residual stream at the correct position near *exactly* recovers performance!

To be clear, the striking thing about this graph isn't that the first row is zero everywhere except for `S2` where it is 1, or that the rows near the end trend to being zero everywhere except for `END` where they are 1; both of these are exactly what we'd expect. The striking things are:

* The computation is highly localized; the relevant information for choosing `IO` over `S` is initially stored in `S2` token and then moved to `END` token without taking any detours.
* The model is basically done after layer 8, and the rest of the layers actually slightly impede performance on this particular task.

(Note - for reference, tokens and their index from the first prompt are on the x-axis. In an abuse of notation, note that the difference here is averaged over *all* 8 prompts, while the labels only come from the *first* prompt.)
</details>


### Exercise - implement head-to-residual patching

```c
Difficulty: 🟠🟠🟠🟠⚪
Importance: 🟠🟠🟠🟠🟠

You should spend up to 20-25 minutes on this exercise.

It's very important to understand how patching works. Many subsequent exercises will build on this one.
```

Now, you should implement the `get_act_patch_resid_pre` function below, which should behave just like the one above. A quick refresher on how to use hooks in this way:

* Hook functions take arguments `tensor: t.Tensor` and `hook: HookPoint`. It's often easier to define a hook function taking more arguments than these, and then use `functools.partial` when it actually comes time to add your hook.
* The function `model.run_with_hooks` takes arguments:
    * The tokens to run (as first argument)
    * `fwd_hooks` - a list of `(hook_name, hook_fn)` tuples. Remember that you can use `utils.get_act_name` to get hook names.
* Tip - it's good practice to have `model.reset_hooks()` at the start of functions which add and run hooks. This is because sometimes hooks fail to be removed (if they cause an error while running). There's nothing more frustrating than fixing a hook error only to get the same error message, not realising that you've failed to clear the broken hook!


```python
def patch_residual_component(
    corrupted_residual_component: Float[Tensor, "batch pos d_model"],
    hook: HookPoint, 
    pos: int, 
    clean_cache: ActivationCache
) -> Float[Tensor, "batch pos d_model"]:
    '''
    Patches a given sequence position in the residual stream, using the value
    from the clean cache.
    '''
    pass

def get_act_patch_resid_pre(
    model: HookedTransformer, 
    corrupted_tokens: Float[Tensor, "batch pos"], 
    clean_cache: ActivationCache, 
    patching_metric: Callable[[Float[Tensor, "batch pos d_vocab"]], float]
) -> Float[Tensor, "layer pos"]:
    '''
    Returns an array of results of patching each position at each layer in the residual
    stream, using the value from the clean cache.

    The results are calculated using the patching_metric function, which should be
    called on the model's logit output.
    '''
    pass


if MAIN:
    act_patch_resid_pre_own = get_act_patch_resid_pre(model, corrupted_tokens, clean_cache, ioi_metric)
    
    t.testing.assert_close(act_patch_resid_pre, act_patch_resid_pre_own)

```

<details>
<summary>Solution</summary>


```python
def patch_residual_component(
    corrupted_residual_component: Float[Tensor, "batch pos d_model"],
    hook: HookPoint, 
    pos: int, 
    clean_cache: ActivationCache
) -> Float[Tensor, "batch pos d_model"]:
    '''
    Patches a given sequence position in the residual stream, using the value
    from the clean cache.
    '''
    # SOLUTION
    corrupted_residual_component[:, pos, :] = clean_cache[hook.name][:, pos, :]
    return corrupted_residual_component

def get_act_patch_resid_pre(
    model: HookedTransformer, 
    corrupted_tokens: Float[Tensor, "batch pos"], 
    clean_cache: ActivationCache, 
    patching_metric: Callable[[Float[Tensor, "batch pos d_vocab"]], float]
) -> Float[Tensor, "layer pos"]:
    '''
    Returns an array of results of patching each position at each layer in the residual
    stream, using the value from the clean cache.

    The results are calculated using the patching_metric function, which should be
    called on the model's logit output.
    '''
    # SOLUTION
    model.reset_hooks()
    seq_len = corrupted_tokens.size(1)
    results = t.zeros(model.cfg.n_layers, seq_len, device="cuda", dtype=t.float32)

    for layer in tqdm(range(model.cfg.n_layers)):
        for position in range(seq_len):
            hook_fn = partial(patch_residual_component, pos=position, clean_cache=clean_cache)
            patched_logits = model.run_with_hooks(
                corrupted_tokens, 
                fwd_hooks = [(utils.get_act_name("resid_pre", layer), hook_fn)], 
            )
            results[layer, position] = patching_metric(patched_logits)

    return results
```
</details>


Once you've passed the tests, you can plot your results.


```python

if MAIN:
    imshow(
        act_patch_resid_pre_own, 
        x=labels, 
        title="Logit Difference From Patched Residual Stream", 
        labels={"x":"Sequence Position", "y":"Layer"},
        width=600 # If you remove this argument, the plot will usually fill the available space
    )

```

<details>
<summary>Solution</summary>

```python
def patch_residual_component(
    corrupted_residual_component: Float[Tensor, "batch pos d_model"],
    hook: HookPoint,
    pos: int,
    clean_cache: ActivationCache
) -> Float[Tensor, "batch pos d_model"]:
    corrupted_residual_component[:, pos, :] = clean_cache[hook.name][:, pos, :]
    return corrupted_residual_component


def get_act_patch_resid_pre(
    model: HookedTransformer,
    corrupted_tokens: Float[Tensor, "batch pos"],
    clean_cache: ActivationCache,
    patching_metric: Callable[[Float[Tensor, "batch pos d_vocab"]], float]
) -> Float[Tensor, "layer pos"]:
    model.reset_hooks()
    results = t.zeros(model.cfg.n_layers, tokens.size(1), device="cuda", dtype=t.float32)

    for layer in tqdm_notebook(range(model.cfg.n_layers)):
        for position in range(corrupted_tokens.shape[1]):
            hook_fn = partial(patch_residual_component, pos=position, clean_cache=clean_cache)
            patched_logits = model.run_with_hooks(
                corrupted_tokens,
                fwd_hooks = [(utils.get_act_name("resid_pre", layer), hook_fn)],
            )
            results[layer, position] = patching_metric(patched_logits)

    return results
```
</details>


## Patching in residual stream by block


Rather than just patching to the residual stream in each layer, we can also patch just after the attention layer or just after the MLP. This gives is a slightly more refined view of which tokens matter and when.

The function `patching.get_act_patch_block_every` works just like `get_act_patch_resid_pre`, but rather than just patching to the residual stream, it patches to `resid_pre`, `attn_out` and `mlp_out`, and returns a tensor of shape `(3, n_layers, seq_len)`.

One important thing to note - we're cycling through the `resid_pre`, `attn_out` and `mlp_out` and only patching one of them at a time, rather than patching all three at once.


```python

if MAIN:
    act_patch_block_every = patching.get_act_patch_block_every(model, corrupted_tokens, clean_cache, ioi_metric)
    
    imshow(
        act_patch_block_every,
        x=labels, 
        facet_col=0, # This argument tells plotly which dimension to split into separate plots
        facet_labels=["Residual Stream", "Attn Output", "MLP Output"], # Subtitles of separate plots
        title="Logit Difference From Patched Attn Head Output", 
        labels={"x": "Sequence Position", "y": "Layer"},
        width=1000,
    )

```

<details>
<summary>What is the interpretation of the second two plots?</summary>

We see that several attention layers are significant but that, matching the residual stream results, early layers matter on `S2`, and later layers matter on `END`, and layers essentially don't matter on any other token. Extremely localised!

As with direct logit attribution, layer 9 is positive and layers 10 and 11 are not, suggesting that the late layers only matter for direct logit effects, but we also see that layers 7 and 8 matter significantly. Presumably these are the heads that move information about which name is duplicated from `S2` to `END`.

In contrast, the MLP layers do not matter much. This makes sense, since this is more a task about moving information than about processing it, and the MLP layers specialise in processing information. The one exception is MLP 0, which matters a lot, but I think this is misleading and just a generally true statement about MLP 0 rather than being about the circuit on this task.

<details> <summary>My takes on MLP0</summary>

It's often observed on GPT-2 Small that MLP0 matters a lot, and that ablating it utterly destroys performance. My current best guess is that the first MLP layer is essentially acting as an extension of the embedding (for whatever reason) and that when later layers want to access the input tokens they mostly read in the output of the first MLP layer, rather than the token embeddings. Within this frame, the first attention layer doesn't do much.

In this framing, it makes sense that MLP0 matters on `S2`, because that's the one position with a different input token!

I'm not entirely sure why this happens, but I would guess that it's because the embedding and unembedding matrices in GPT-2 Small are the same. This is pretty unprincipled, as the tasks of embedding and unembedding tokens are <i>not</i> inverses, but this is common practice, and plausibly models want to dedicate some parameters to overcoming this.

I only have suggestive evidence of this, and would love to see someone look into this properly!
</details>
</details>


### Exercise (optional) - implement head-to-block patching

```c
Difficulty: 🟠🟠⚪⚪⚪
Importance: 🟠🟠⚪⚪⚪

You should spend up to ~10 minutes on this exercise. 

Most code can be copied from the last exercise.
```

If you want, you can implement the `get_act_patch_resid_pre` function for fun, although it's similar enough to the previous exercise that doing this isn't compulsory.


```python
def get_act_patch_block_every(
    model: HookedTransformer, 
    corrupted_tokens: Float[Tensor, "batch pos"], 
    clean_cache: ActivationCache, 
    patching_metric: Callable[[Float[Tensor, "batch pos d_vocab"]], float]
) -> Float[Tensor, "layer pos"]:
    '''
    Returns an array of results of patching each position at each layer in the residual
    stream, using the value from the clean cache.

    The results are calculated using the patching_metric function, which should be
    called on the model's logit output.
    '''
    pass


```

```python

if MAIN:
    act_patch_block_every_own = get_act_patch_block_every(model, corrupted_tokens, clean_cache, ioi_metric)
    
    t.testing.assert_close(act_patch_block_every, act_patch_block_every_own)
    
    imshow(
        act_patch_block_every_own,
        x=labels, 
        facet_col=0,
        facet_labels=["Residual Stream", "Attn Output", "MLP Output"],
        title="Logit Difference From Patched Attn Head Output", 
        labels={"x": "Sequence Position", "y": "Layer"},
        width=1000
    )

```

<details>
<summary>Solution</summary>


```python
def get_act_patch_block_every(
    model: HookedTransformer, 
    corrupted_tokens: Float[Tensor, "batch pos"], 
    clean_cache: ActivationCache, 
    patching_metric: Callable[[Float[Tensor, "batch pos d_vocab"]], float]
) -> Float[Tensor, "layer pos"]:
    '''
    Returns an array of results of patching each position at each layer in the residual
    stream, using the value from the clean cache.

    The results are calculated using the patching_metric function, which should be
    called on the model's logit output.
    '''
    # SOLUTION
    model.reset_hooks()
    results = t.zeros(3, model.cfg.n_layers, tokens.size(1), device="cuda", dtype=t.float32)

    for component_idx, component in enumerate(["resid_pre", "attn_out", "mlp_out"]):
        for layer in tqdm(range(model.cfg.n_layers)):
            for position in range(corrupted_tokens.shape[1]):
                hook_fn = partial(patch_residual_component, pos=position, clean_cache=clean_cache)
                patched_logits = model.run_with_hooks(
                    corrupted_tokens, 
                    fwd_hooks = [(utils.get_act_name(component, layer), hook_fn)], 
                )
                results[component_idx, layer, position] = patching_metric(patched_logits)

    return results
```
</details>


## Head Patching


We can refine the above analysis by patching in individual heads! This is somewhat more annoying, because there are now three dimensions `(head_index, position and layer)`.

The code below patches a head's output over all sequence positions, and returns the results (for each head in the model).


```python

if MAIN:
    act_patch_attn_head_out_all_pos = patching.get_act_patch_attn_head_out_all_pos(
        model, 
        corrupted_tokens, 
        clean_cache, 
        ioi_metric
    )

```

```python

if MAIN:
    imshow(
        act_patch_attn_head_out_all_pos, 
        labels={"y": "Layer", "x": "Head"}, 
        title="attn_head_out Activation Patching (All Pos)",
        width=600
    )

```

<details>
<summary>What are the interpretations of this graph? Which heads do you think are important?</summary>

We see some of the heads that we observed in our attention plots at the end of last section (e.g. `9.9` having a large positive score, and `10.7` having a large negative score). But we can also see some other important heads, for instance:

* In layers 7-8 there are several important heads. We might deduce that these are the ones responsible for moving information from `S2` to `end`.
* In the earlier layers, there are some more important heads (e.g. `3.0` and `5.5`). We might guess these are performing some primitive logic, e.g. causing the second `" John"` token to attend to previous instances of itself.

</details>


### Exercise - implement head-to-head patching

```c
Difficulty: 🟠🟠🟠⚪⚪
Importance: 🟠🟠🟠🟠⚪

You should spend up to 10-15 minutes on this exercise. 

Again, it should be similar to the first patching exercise (you can copy code).
```

You should implement your own version of this patching function below.

You'll need to define a new hook function, but most of the code from the previous exercise should be reusable.

<details>
<summary>Help - I'm not sure what hook name to use for my patching.</summary>

You should patch at:

```python
utils.get_act_name("z", layer)
```

This is the linear combination of value vectors, i.e. it's the thing you multiply by $W_O$ before adding back into the residual stream. There's no point patching after the $W_O$ multiplication, because it will have the same effect, but take up more memory (since `d_model` is larger than `d_head`).
</details>


```python
def patch_head_vector(
    corrupted_head_vector: Float[Tensor, "batch pos head_index d_head"],
    hook: HookPoint, 
    head_index: int, 
    clean_cache: ActivationCache
) -> Float[Tensor, "batch pos head_index d_head"]:
    '''
    Patches the output of a given head (before it's added to the residual stream) at
    every sequence position, using the value from the clean cache.
    '''
    pass

def get_act_patch_attn_head_out_all_pos(
    model: HookedTransformer, 
    corrupted_tokens: Float[Tensor, "batch pos"], 
    clean_cache: ActivationCache, 
    patching_metric: Callable
) -> Float[Tensor, "layer head"]:
    '''
    Returns an array of results of patching at all positions for each head in each
    layer, using the value from the clean cache.

    The results are calculated using the patching_metric function, which should be
    called on the model's logit output.
    '''
    pass


if MAIN:
    act_patch_attn_head_out_all_pos_own = get_act_patch_attn_head_out_all_pos(model, corrupted_tokens, clean_cache, ioi_metric)
    
    t.testing.assert_close(act_patch_attn_head_out_all_pos, act_patch_attn_head_out_all_pos_own)

```

```python

if MAIN:
    imshow(
        act_patch_attn_head_out_all_pos_own,
        title="Logit Difference From Patched Attn Head Output", 
        labels={"x":"Head", "y":"Layer"},
        width=600
    )

```

<details>
<summary>Solution</summary>


```python
def patch_head_vector(
    corrupted_head_vector: Float[Tensor, "batch pos head_index d_head"],
    hook: HookPoint, 
    head_index: int, 
    clean_cache: ActivationCache
) -> Float[Tensor, "batch pos head_index d_head"]:
    '''
    Patches the output of a given head (before it's added to the residual stream) at
    every sequence position, using the value from the clean cache.
    '''
    # SOLUTION
    corrupted_head_vector[:, :, head_index] = clean_cache[hook.name][:, :, head_index]
    return corrupted_head_vector

def get_act_patch_attn_head_out_all_pos(
    model: HookedTransformer, 
    corrupted_tokens: Float[Tensor, "batch pos"], 
    clean_cache: ActivationCache, 
    patching_metric: Callable
) -> Float[Tensor, "layer head"]:
    '''
    Returns an array of results of patching at all positions for each head in each
    layer, using the value from the clean cache.

    The results are calculated using the patching_metric function, which should be
    called on the model's logit output.
    '''
    # SOLUTION
    model.reset_hooks()
    results = t.zeros(model.cfg.n_layers, model.cfg.n_heads, device="cuda", dtype=t.float32)

    for layer in tqdm(range(model.cfg.n_layers)):
        for head in range(model.cfg.n_heads):
            hook_fn = partial(patch_head_vector, head_index=head, clean_cache=clean_cache)
            patched_logits = model.run_with_hooks(
                corrupted_tokens, 
                fwd_hooks = [(utils.get_act_name("z", layer), hook_fn)], 
                return_type="logits"
            )
            results[layer, head] = patching_metric(patched_logits)

    return results
```
</details>


## Decomposing Heads


Finally, we'll look at one more example of activation patching.

Decomposing attention layers into patching in individual heads has already helped us localise the behaviour a lot. But we can understand it further by decomposing heads. An attention head consists of two semi-independent operations - calculating *where* to move information from and to (represented by the attention pattern and implemented via the QK-circuit) and calculating *what* information to move (represented by the value vectors and implemented by the OV circuit). We can disentangle which of these is important by patching in just the attention pattern *or* the value vectors. See [A Mathematical Framework](https://transformer-circuits.pub/2021/framework/index.html) or [Neel's walkthrough video](https://www.youtube.com/watch?v=KV5gbOmHbjU) for more on this decomposition.


A useful function for doing this is `get_act_patch_attn_head_all_pos_every`. Rather than just patching on head output (like the previous one), it patches on:
* Output (this is equivalent to patching the value the head writes to the residual stream)
* Querys (i.e. the patching the query vectors, without changing the key or value vectors)
* Keys
* Values
* Patterns (i.e. the attention patterns).

Again, note that this function isn't patching multiple things at once. It's looping through each of these five, and getting the results from patching them one at a time.


```python

if MAIN:
    act_patch_attn_head_all_pos_every = patching.get_act_patch_attn_head_all_pos_every(
        model, 
        corrupted_tokens, 
        clean_cache, 
        ioi_metric
    )

```

```python

if MAIN:
    imshow(
        act_patch_attn_head_all_pos_every, 
        facet_col=0, 
        facet_labels=["Output", "Query", "Key", "Value", "Pattern"],
        title="Activation Patching Per Head (All Pos)", 
        labels={"x": "Head", "y": "Layer"},
    )

```

### Exercise (optional) - implement head-to-head-input patching

```c
Difficulty: 🟠🟠⚪⚪⚪
Importance: 🟠🟠⚪⚪⚪

You should spend up to ~10 minutes on this exercise. 

Most code can be copied from the last exercise.
```

Again, if you want to implement this yourself then you can do so below, but it isn't a compulsory exercise because it isn't conceptually different from the previous exercises. If you don't implement it, then you should still look at the solution to make sure you understand what's going on.


```python
def patch_attn_patterns(
    corrupted_head_vector: Float[Tensor, "batch head_index pos_q pos_k"],
    hook: HookPoint, 
    head_index: int, 
    clean_cache: ActivationCache
) -> Float[Tensor, "batch pos head_index d_head"]:
    '''
    Patches the attn patterns of a given head at every sequence position, using 
    the value from the clean cache.
    '''
    pass

def get_act_patch_attn_head_all_pos_every(
    model: HookedTransformer,
    corrupted_tokens: Float[Tensor, "batch pos"],
    clean_cache: ActivationCache,
    patching_metric: Callable
) -> Float[Tensor, "layer head"]:
    '''
    Returns an array of results of patching at all positions for each head in each
    layer (using the value from the clean cache) for output, queries, keys, values
    and attn pattern in turn.

    The results are calculated using the patching_metric function, which should be
    called on the model's logit output.
    '''
    pass


if MAIN:
    act_patch_attn_head_all_pos_every_own = get_act_patch_attn_head_all_pos_every(
        model,
        corrupted_tokens,
        clean_cache,
        ioi_metric
    )
    
    t.testing.assert_close(act_patch_attn_head_all_pos_every, act_patch_attn_head_all_pos_every_own)

```

```python

if MAIN:
    imshow(
        act_patch_attn_head_all_pos_every_own,
        facet_col=0,
        facet_labels=["Output", "Query", "Key", "Value", "Pattern"],
        title="Activation Patching Per Head (All Pos)",
        labels={"x": "Head", "y": "Layer"},
        width=1200
    )

```

<details>
<summary>Solution</summary>


```python
def patch_attn_patterns(
    corrupted_head_vector: Float[Tensor, "batch head_index pos_q pos_k"],
    hook: HookPoint, 
    head_index: int, 
    clean_cache: ActivationCache
) -> Float[Tensor, "batch pos head_index d_head"]:
    '''
    Patches the attn patterns of a given head at every sequence position, using 
    the value from the clean cache.
    '''
    # SOLUTION
    corrupted_head_vector[:, head_index] = clean_cache[hook.name][:, head_index]
    return corrupted_head_vector

def get_act_patch_attn_head_all_pos_every(
    model: HookedTransformer,
    corrupted_tokens: Float[Tensor, "batch pos"],
    clean_cache: ActivationCache,
    patching_metric: Callable
) -> Float[Tensor, "layer head"]:
    '''
    Returns an array of results of patching at all positions for each head in each
    layer (using the value from the clean cache) for output, queries, keys, values
    and attn pattern in turn.

    The results are calculated using the patching_metric function, which should be
    called on the model's logit output.
    '''
    # SOLUTION
    results = t.zeros(5, model.cfg.n_layers, model.cfg.n_heads, device="cuda", dtype=t.float32)
    # Loop over each component in turn
    for component_idx, component in enumerate(["z", "q", "k", "v", "pattern"]):
        for layer in tqdm(range(model.cfg.n_layers)):
            for head in range(model.cfg.n_heads):
                # Get different hook function if we're doing attention probs
                hook_fn_general = patch_attn_patterns if component == "pattern" else patch_head_vector
                hook_fn = partial(hook_fn_general, head_index=head, clean_cache=clean_cache)
                # Get patched logits
                patched_logits = model.run_with_hooks(
                    corrupted_tokens,
                    fwd_hooks = [(utils.get_act_name(component, layer), hook_fn)],
                    return_type="logits"
                )
                results[component_idx, layer, head] = patching_metric(patched_logits)

    return results
```
</details>


Note - we can do this in an even more fine-grained way; the function `patching.get_act_patch_attn_head_by_pos_every` (i.e. same as above but replacing `all_pos` with `by_pos`) will give you the same decomposition, but by sequence position *as well as* by layer, head and component. The same holds for the `patching.get_act_patch_attn_head_out_all_pos` function earlier (replace `all_pos` with `by_pos`). These functions are unsurprisingly pretty slow though!


This plot has some striking features. For instance, this shows us that we have at least three different groups of heads:

* Earlier heads (`3.0`, `5.5`, `6.9`) which matter because of their attention patterns (specifically their query vectors).
* Middle heads in layers 7 & 8 (`7.3`, `7.9`, `8.6`, `8.10`) seem to matter more because of their value vectors.
* Later heads which improve the logit difference (`9.9`, `10.0`), which matter because of their query vectors.

Question - what is the significance of the results for the middle heads (i.e. the important ones in layers 7 & 8)? In particular, how should we interpret the fact that value patching has a much bigger effect than the other two forms of patching?

*Hint - if you're confused, try plotting the attention patterns of heads `7.3`, `7.9`, `8.6`, `8.10`. You can mostly reuse the code from above when we displayed the output of attention heads.*

<details>
<summary>Code to plot attention heads</summary>

```python
# Get the heads with largest value patching
# (we know from plot above that these are the 4 heads in layers 7 & 8)
k = 4
top_heads = topk_of_Nd_tensor(act_patch_attn_head_all_pos_every[3], k=k)

# Get all their attention patterns
attn_patterns_for_important_heads: Float[Tensor, "head q k"] = t.stack([
    cache["pattern", layer][:, head].mean(0)
        for layer, head in top_heads
])

# Display results
display(HTML(f"<h2>Top {k} Logit Attribution Heads (from value-patching)</h2>"))
display(cv.attention.attention_patterns(
    attention = attn_patterns_for_important_heads,
    tokens = model.to_str_tokens(tokens[0]),
    attention_head_names = [f"{layer}.{head}" for layer, head in top_heads],
))
```
</details>

<details>
<summary>Answer</summary>

The attention patterns show us that these heads attend from `END` to `S2`, so we can guess that they're responsible for moving information from `S2` to `END` which is used to determine the answer. This agrees with our earlier results, when we saw that most of the information gets moved over layers 7 & 8.

The fact that value patching is the most important thing for them suggests that the interesting computation goes into **what information they move from `S2` to `end`**, rather than **why `end` attends to `S2`**. See the diagram below if you're confused why we can draw this inference.

<img src="https://raw.githubusercontent.com/callummcdougall/computational-thread-art/master/example_images/misc/k-vs-v-patching-explained.png" width="900">

</details>


## Consolidating Understanding


OK, let's zoom out and reconsolidate. Here's a recap of the most important observations we have so far:

* Heads `9.9`, `9.6`, and `10.0` are the most important heads in terms of directly writing to the residual stream. In all these heads, the `END` attends strongly to the `IO`.
    * We discovered this by taking the values written by each head in each layer to the residual stream, and projecting them along the logit diff direction by using `residual_stack_to_logit_diff`. We also looked at attention patterns using `circuitsvis`.
    * <span style="color:turquoise">**This suggests that these heads are copying `IO` to `end`, to use it as the predicted next token.**</span>
    * The question then becomes *"how do these heads know to attend to this token, and not attend to `S`?"*

<br>

* All the action is on `S2` until layer 7 and then transitions to `END`. And that attention layers matter a lot, MLP layers not so much (apart from MLP0, likely as an extended embedding).
    * We discovered this by doing **activation patching** on `resid_pre`, `attn_out`, and `mlp_out`.
    * <span style="color:turquoise">**This suggests that there is a cluster of heads in layers 7 & 8, which move information from `S2` to `END`. We deduce that this information is how heads `9.9`, `9.6` and `10.0` know to attend to `IO`.**</span>
    * The question then becomes *"what is this information, how does it end up in the `S2` token, and how does `END` know to attend to it?"*

<br>

* The significant heads in layers 7 & 8 are `7.3`, `7.9`, `8.6`, `8.10`. These heads have high activation patching values for their value vectors, less so for their queries and keys.
    * We discovered this by doing **activation patching** on the value inputs for these heads.
    * <span style="color:turquoise">**This supports the previous observation, and it tells us that the interesting computation goes into *what gets moved* from `S2` to `END`, rather than the fact that `END` attends to `S2`.**</span>.
    * We still don't know: *"what is this information, and how does it end up in the `S2` token?"*

<br>

* As well as the 2 clusters of heads given above, there's a third cluster of important heads: early heads (e.g. `3.0`, `5.5`, `6.9`) whose query vectors are particularly important for getting good performance.
    * We discovered this by doing **activation patching** on the query inputs for these heads.


With all this in mind, can you come up with a theory for what these three heads are doing, and come up with a simple model of the whole circuit?

*Hint - if you're still stuck, try plotting the attention pattern of head `3.0`. The patterns of `5.5` and `6.9` might seem a bit confusing at first (they add complications to the "simplest possible picture" of how the circuit works); we'll discuss them later so they don't get in the way of understanding the core of the circuit.*

<details>
<summary>Answer (and simple diagram of circuit)</summary>

If you plotted the attention pattern for head `3.0`, you should have seen that `S2` paid attention to `S1`. This suggests that the early heads are detecting when the destination token is a duplicate. So the information that the subject is a duplicate gets stored in `S2`.

How can the information that the subject token is a duplicate help us predict the token after `end`? Well, the correct answer (the `IO` token) is the non-duplicated token. So we can infer that the information that the subject token is a duplicate is used to *inhibit* the attention of the late heads to the duplicated token, and they instead attend to the non-duplicated token.

To summarise the second half of the circuit: information about this duplicated token is then moved from `S2` to `end` by the middle cluster of heads `7.3`, `7.9`, `8.6` and `8.10`, and this information goes into the queries of the late heads `9.9`, `9.6` and `10.0`, making them *inhibit* their attention to the duplicated token. Instead, they attend to `IO` (copying this token directly to the logits).

This picture of the circuit turns out to be mostly right. It misses out on some subtleties which we'll discuss shortly, but it's a good rough picture to have in your head. We might illustrate this as follows:

<img src="https://raw.githubusercontent.com/callummcdougall/computational-thread-art/master/example_images/misc/ioi-main-simple.png" width="1000">

Explanation:

* We call the early heads **DTH** (duplicate token heads), their job is to detect that `S2` is a duplicate.
* The second group of heads are called **SIH** (S-inhibition heads), their job is to move the duplicated token information from `S2` to `END`. We've illustrated this as them moving the positional information, but in principle this could also be token embedding information (more on this in the final section).
* The last group of heads are called **NMH** (name mover heads), their job is to copy the `IO` token to the `END` token, where it is used as the predicted next token (thanks to the S-inihbition heads, these heads don't pay attention to the `S` token).

Note - if you're still confused about how to interpret this diagram, but you understand induction circuits and how they work, it might help to compare this diagram to one written in the same style which I made for [induction circuits](https://raw.githubusercontent.com/callummcdougall/computational-thread-art/master/example_images/misc/ih-simple.png). Also, if you've read my induction heads [LessWrong post](https://www.lesswrong.com/posts/TvrfY4c9eaGLeyDkE/induction-heads-illustrated) and you're confused about how this style of diagram is different from that one, [here](https://raw.githubusercontent.com/callummcdougall/computational-thread-art/master/example_images/misc/ih-compared.png) is an image comparing the two diagrams (for induction heads) and explaining how they differ.

</details>


Now, let's flesh out this picture a bit more by comparing our results to the paper results. Below is a more complicated version of the diagram in the dropdown above, which also labels the important heads. The diagram is based on the paper's [original diagram](https://res.cloudinary.com/lesswrong-2-0/image/upload/v1672942728/mirroredImages/3ecs6duLmTfyra3Gp/h5icqzpyuhu4mqvfjhvw.png). Don't worry if you don't understand everything in this diagram; the boundaries of the circuit are fuzzy and the "role" of every head is in this circuit is a leaky abstraction. Rather, this diagram is meant to point your intuitions in the right direction for better understanding this circuit.

<details>
<summary>Diagram of large circuit</summary>

<img src="https://raw.githubusercontent.com/callummcdougall/computational-thread-art/master/example_images/misc/ioi-main-full-c.png" width="1250">
</details>




Here are the main ways it differs from the one above:




#### Induction heads

Rather than just having duplicate token heads in the first cluster of heads, we have two other types of heads as well: previous token heads and induction heads. The induction heads do the same thing as the duplicate token heads, via an induction mechanism. They cause token `S2` to attend to `S1+1` (mediated by the previous token heads), and their output is used as both a pointer to `S1` and as a signal that `S1` is duplicated (more on the distinction between these two in the paragraph "Position vs token information being moved" below).

*(Note - the original paper's diagram implies the induction heads and duplicate token heads compose with each other. This is misleading, and is not the case.)*

Why are induction heads used in this circuit? We'll dig into this more in the bonus section, but one likely possibility is that induction heads are just a thing that forms very early on in training by default, and so it makes sense for the model to repurpose this already-existing machinery for this job. See [this paper](https://transformer-circuits.pub/2022/in-context-learning-and-induction-heads/index.html) for more on induction heads, and how / why they form.


#### Negative & Backup name mover heads

Earlier, we saw that some heads in later layers were actually harming performance. These heads turn out to be doing something pretty similar to name mover heads, but in reverse (i.e. they inhibit the correct answer). It's not obvious why the model does this; the paper speculates that these heads might help the model "hedge" so as to avoid high cross-entropy loss when making mistakes.

Backup name mover heads are possibly even weirder. It turns out that when we **ablate** the name mover heads, these ones pick up the slack and do the task anyway (even though they don't seem to do it when the NMHs aren't ablated). This is an example of **built-in redundancy** in the model. One possible explanation is that this resulted from the model being trained with dropout, although this explanation isn't fully satisfying (models trained without dropout still seem to have BNMHs, although they aren't as strong as they are in this model). Like with induction heads, we'll dig into this more in the final section.


#### Positional vs token information

There are 2 kinds of S-inhibition heads shown in the diagram - ones that inhibit based on positional information (pink), and ones that inhibit based on token information (purple). It's not clear which heads are doing which (and in fact some heads might be doing both!).

The paper has an ingenious way of teasing apart which type of information is being used by which of the S-inhibition heads, which we'll discuss in the final section.


#### K-composition in S-inhibition heads

When we did activation patching on the keys and values of S-inhibition heads, we found that the values were important and the keys weren't. We concluded that K-composition isn't really happening in these heads, and `END` must be paying attention to `S2` for reasons other than the duplicate token information (e.g. it might just be paying attention to the closest name, or to any names which aren't separated from it by a comma). Although this is mostly true, it turns out that there is a bit of K-composition happening in these heads. We can think of this as the duplicate token heads writing the "duplicated" flag to the residual stream (without containing any information about the identity and position of this token), and this flag is being used by the keys of the S-inhibition heads (i.e. they make `END` pay attention to `S2`). In the diagram, this is represented by the dark grey boxes (rather than just the light grey boxes we had in the simplified version). We haven't seen any evidence for this happening yet, but we will in the next section (when we look at path patching).

Note - whether the early heads are writing positional information or "duplicate flag" information to the residual stream is not necessarily related to whether the head is an induction head or a duplicate token head. In principle, either type of head could write either type of information.




""", unsafe_allow_html=True)


def section_4():

    st.sidebar.markdown(r"""

## Table of Contents

<ul class="contents">
    <li class='margtop'><a class='contents-el' href='#setup'>Setup</a></li>
    <li class='margtop'><a class='contents-el' href='#what-is-path-patching'>What is path patching?</a></li>
    <li class='margtop'><a class='contents-el' href='#path-patching:-name-mover-heads'>Path Patching: Name Mover Heads</a></li>
    <li><ul class="contents">
        <li><a class='contents-el' href='#exercise-implement-path-patching-to-the-final-residual-stream-value'><b>Exercise</b> - implement path patching to the final residual stream value</a></li>
    </ul></li>
    <li class='margtop'><a class='contents-el' href='#path-patching:-s-inhibition-heads'>Path Patching: S-Inhibition Heads</a></li>
    <li><ul class="contents">
        <li><a class='contents-el' href='#exercise-implement-path-patching-from-head-to-head'><b>Exercise</b> - implement path patching from head to head</a></li>
</ul></li>""", unsafe_allow_html=True)

    st.markdown(r"""

# 4️⃣ Path Patching


> ##### Learning objectives
> 
> * Understand the idea of path patching, and how it differs from activation patching
> * Implement path patching from scratch (i.e. using hooks)
> * Replicate several of the results in the [IOI paper](https://arxiv.org/abs/2211.00593)


This section will be a lot less conceptual and exploratory than the last two sections, and a lot more technical and rigorous. You'll learn what path patching is and how it works, and you'll use it to replicate many of the paper's results (as well as some other paper results not related to path patching).


## Setup


Here, we'll be more closely following the setup that the paper's authors used, rather than the rough-and-ready exploration we used in the first few sections. To be clear, a lot of the rigour that we'll be using in the setup here isn't necessary if you're just starting to investigate a model's circuit. This rigour is necessary if you're publishing a paper, but it can take a lot of time and effort!


```python
from part3_indirect_object_identification.ioi_dataset import NAMES, IOIDataset

```

The dataset we'll be using is an instance of `IOIDataset`, which is generated by randomly choosing names from the `NAMES` list (as well as sentence templates and objects from different lists). You can look at the `ioi_dataset.py` file to see details of how this is done.

(Note - you can reduce `N` if you're getting memory errors from running this code. If you're still getting memory errors from `N = 10` then you're recommended to switch to Colab, or to use a virtual machine e.g. via Lambda Labs.)


```python

if MAIN:
    N = 25
    ioi_dataset = IOIDataset(
        prompt_type="mixed",
        N=N,
        tokenizer=model.tokenizer,
        prepend_bos=False,
        seed=1,
        device=str(device)
    )

```

This dataset has a few useful attributes & methods. Here are the main ones you should be aware of for these exercises:

* `toks` is a tensor of shape `(batch_size, max_seq_len)` containing the token IDs (i.e. this is what you pass to your model)
* `s_tokenIDs` and `io_tokenIDs` are lists containing the token IDs for the subjects and objects
* `sentences` is a list containing the sentences (as strings)
* `word_idx` is a dictionary mapping word types (e.g. `"S1"`, `"S2"`, `"IO"` or `"end"`) to tensors containing the positions of those words for each sequence in the dataset.
    * This is particularly handy for indexing, since the positions of the subject, indirect object, and end tokens are no longer the same in every sentence like they were in previous sections.


Firstly, what dataset should we use for patching? In the previous section we just flipped the subject and indirect object tokens around, which meant the direction of the signal was flipped around. However, what we'll be doing here is a bit more principled - rather than flipping the IOI signal, we'll be erasing it. We do this by constructing a new dataset from `ioi_dataset` which replaces every name with a different random name. This way, the sentence structure stays the same, but all information related to the actual indirect object identification  task (i.e. the identities and positions of repeated names) has been erased.

For instance, given the sentence `"When John and Mary went to the shops, John gave the bag to Mary"`, the corresponding sentence in the ABC dataset might be `"When Edward and Laura went to the shops, Adam gave the bag to Mary"`. We would expect the residual stream for the latter prompt to carry no token or positional information which could help it solve the IOI task (i.e. favouring `Mary` over `John`, or favouring the 2nd token over the 4th token).

We define this dataset below. Note the syntax of the `gen_flipped_prompts` method - the letters tell us how to replace the names in the sequence. For instance, `ABB->XYZ` tells us to take sentences of the form `"When Mary and John went to the store, John gave a drink to Mary"` with `"When [X] and [Y] went to the store, [Z] gave a drink to Mary"` for 3 independent randomly chosen names `[X]`, `[Y]` and `[Z]`. We'll use this function more in the bonus section, when we're trying to disentangle positional and token signals (since we can also do fun things like `ABB->BAB` to swap the first two names, etc).


```python

if MAIN:
    abc_dataset = ioi_dataset.gen_flipped_prompts("ABB->XYZ, BAB->XYZ")

```

Let's take a look at this dataset. We'll define a helper function `make_table`, which prints out tables after being fed columns rather than rows (don't worry about the syntax, it's not important).


```python
def format_prompt(sentence: str) -> str:
    '''Format a prompt by underlining names (for rich print)'''
    return re.sub("(" + "|".join(NAMES) + ")", lambda x: f"[u bold dark_orange]{x.group(0)}[/]", sentence) + "\n"


def make_table(cols, colnames, title="", n_rows=5, decimals=4):
    '''Makes and displays a table, from cols rather than rows (using rich print)'''
    table = Table(*colnames, title=title)
    rows = list(zip(*cols))
    f = lambda x: x if isinstance(x, str) else f"{x:.{decimals}f}"
    for row in rows[:n_rows]:
        table.add_row(*list(map(f, row)))
    rprint(table)

```

```python

if MAIN:
    make_table(
        colnames = ["IOI prompt", "IOI subj", "IOI indirect obj", "ABC prompt"],
        cols = [
            map(format_prompt, ioi_dataset.sentences), 
            model.to_string(ioi_dataset.s_tokenIDs).split(), 
            model.to_string(ioi_dataset.io_tokenIDs).split(), 
            map(format_prompt, abc_dataset.sentences), 
        ],
        title = "Sentences from IOI vs ABC distribution",
    )

```

Next, we'll define functions similar to the ones from previous sections. We've just given you these, rather than making you repeat the exercise of writing them (although you should compare these functions to the ones you wrote earlier, and make sure you understand how they work).

We'll call these functions something slightly different, so as not to pollute namespace.


```python

if MAIN:
    def logits_to_ave_logit_diff_2(logits: Float[Tensor, "batch seq d_vocab"], ioi_dataset: IOIDataset = ioi_dataset, per_prompt=False):
        '''
        Returns logit difference between the correct and incorrect answer.
    
        If per_prompt=True, return the array of differences rather than the average.
        '''
        
        # Only the final logits are relevant for the answer
        # Get the logits corresponding to the indirect object / subject tokens respectively
        io_logits: Float[Tensor, "batch"] = logits[range(logits.size(0)), ioi_dataset.word_idx["end"], ioi_dataset.io_tokenIDs]
        s_logits: Float[Tensor, "batch"] = logits[range(logits.size(0)), ioi_dataset.word_idx["end"], ioi_dataset.s_tokenIDs]
        # Find logit difference
        answer_logit_diff = io_logits - s_logits
        return answer_logit_diff if per_prompt else answer_logit_diff.mean()
    
    
    model.reset_hooks(including_permanent=True)
    
    ioi_logits_original, ioi_cache = model.run_with_cache(ioi_dataset.toks)
    abc_logits_original, abc_cache = model.run_with_cache(abc_dataset.toks)
    
    ioi_per_prompt_diff = logits_to_ave_logit_diff_2(ioi_logits_original, per_prompt=True)
    abc_per_prompt_diff = logits_to_ave_logit_diff_2(abc_logits_original, per_prompt=True)
    
    ioi_average_logit_diff = logits_to_ave_logit_diff_2(ioi_logits_original).item()
    abc_average_logit_diff = logits_to_ave_logit_diff_2(abc_logits_original).item()

```

```python

if MAIN:
    print(f"Average logit diff (IOI dataset): {ioi_average_logit_diff:.4f}")
    print(f"Average logit diff (ABC dataset): {abc_average_logit_diff:.4f}")
    
    make_table(
        colnames = ["IOI prompt", "IOI logit diff", "ABC prompt", "ABC logit diff"],
        cols = [
            map(format_prompt, ioi_dataset.sentences), 
            ioi_per_prompt_diff,
            map(format_prompt, abc_dataset.sentences), 
            abc_per_prompt_diff,
        ],
        title = "Sentences from IOI vs ABC distribution",
    )

```

Note that we're always measuring performance ***with respect to the correct answers for the IOI dataset, not the ABC dataset***, because we want our ABC dataset to carry no information that helps with the IOI task (hence patching it in gives us signals which are totally uncorrelated with the correct answer). For instance, the model will obviously not complete sentences like `"When Max and Victoria got a snack at the store, Clark decided to give it to"` with the name `"Tyler"`.


Finally, let's define a new `ioi_metric` function which works for our new data.

In order to match the paper's results, we'll use a different convention here. 0 means performance is the same as on the IOI dataset (i.e. hasn't been harmed in any way), and -1 means performance is the same as on the ABC dataset (i.e. the model has completely lost the ability to distinguish between the subject and indirect object).

Again, we'll call this function something slightly different. 


```python

if MAIN:
    def ioi_metric_2(
        logits: Float[Tensor, "batch seq d_vocab"],
        clean_logit_diff: float = ioi_average_logit_diff,
        corrupted_logit_diff: float = abc_average_logit_diff,
        ioi_dataset: IOIDataset = ioi_dataset,
    ) -> float:
        '''
        We calibrate this so that the value is 0 when performance isn't harmed (i.e. same as IOI dataset), 
        and -1 when performance has been destroyed (i.e. is same as ABC dataset).
        '''
        patched_logit_diff = logits_to_ave_logit_diff_2(logits, ioi_dataset)
        return (patched_logit_diff - clean_logit_diff) / (clean_logit_diff - corrupted_logit_diff)
    
    
    print(f"IOI metric (IOI dataset): {ioi_metric_2(ioi_logits_original):.4f}")
    print(f"IOI metric (ABC dataset): {ioi_metric_2(abc_logits_original):.4f}")

```

## What is path patching?


In the previous section, we looked at activation patching, which answers questions like *what would happen if you took an attention head, and swapped the value it writes to the residual stream with the value it would have written under a different distribution, while keeping everything else the same?*. This proved to be a good way to examine the role of individual components like attention heads, and it allowed us to perform some more subtle analysis like patching keys / queries / values in turn to figure out which of them were more important for which heads.

However, when we're studying a circuit, rather than just swapping out an entire attention head, we might want to ask more nuanced questions like *what would happen if the direct input from attention head $A$ to head $B$ (where $B$ comes after $A$) was swapped out with the value it would have been under a different distribution, while keeping everything else the same?*. Rather than answering the general question of how important attention heads are, this answers the more specific question of how important the circuit formed by connecting up these two attention heads is. Path patching is designed to answer questions like these.


The following diagrams might help explain the difference between activation and path patching in transformers. Recall that activation patching looked like:

<img src="https://raw.githubusercontent.com/callummcdougall/computational-thread-art/master/example_images/misc/simpler-patching-2c.png" width="420">

where the black and green distributions are our clean and corrupted datasets respectively (so this would be `ioi_dataset` and `abc_dataset`). In contrast, path patching involves replacing **edges** rather than **nodes**. In the diagram below, we're replacing the edge $D \to G$ with what it would be on the corrupted distribution. So in our patched run, $G$ is calculated just like it would be on the clean distribution, but as if the **direct** input from $D$ had come from the corrupted distribution instead.

<img src="https://raw.githubusercontent.com/callummcdougall/computational-thread-art/master/example_images/misc/simpler-patching-3c.png" width="560">


Unfortunately, for a transformer, this is easier to describe than to actually implement. This is because the "nodes" are attention heads, and the "edges" are all tangled together in the residual stream (that is to say, it's not clear how one could change the value of one edge without without affecting every path that includes that edge). The solution is to use the 3-step algorithm shown in the diagram below (which reads from right to left).

Terminology note - we call head $D$ the **sender node**, and head $G$ the **receiver node**. Also, by "freezing" nodes, we mean "patch with the value that is the same as the input". For instance, if we didn't freeze head $H$ in step 2 below, it would have a different value because it would be affected by the corrupted value of head $D$.

<img src="https://raw.githubusercontent.com/callummcdougall/computational-thread-art/master/example_images/misc/simpler-patching-4c.png" width="900">


Let's make this concrete, and take a simple 3-layer transformer with 2 heads per layer. Let's perform path patching on the edge from head `0.0` to `2.0` (terminology note: `0.0` is the **sender**, and `2.0` is the **receiver**). Note that here, we're considering "direct paths" as anything that doesn't go through another attention head (so it can go through any combination of MLPs). Intuitively, the nodes (attention heads) are the only things that can move information around in the model, and this is the thing we want to study. In contrast, MLPs just perform information processing, and they're not as interesting for this task.

Our 3-step process (reading from right to left) looks like:

<img src="https://raw.githubusercontent.com/callummcdougall/computational-thread-art/master/example_images/misc/path-patching-alg-transformers-4.png" width="700">

(Note - in this diagram, the uncoloured nodes indicate we aren't doing any patching; we're just allowing them to be computed from the values of nodes which are downstream of it.)


Why does this work? If you stare at the middle picture above for long enough, you'll realise that the contribution from every non-direct path from `0.0` $\to$ `2.0` is the same as it would be on the clean distribution, while all the direct paths' contributions are the same as they would be on the corrupted distribution. 

<img src="https://raw.githubusercontent.com/callummcdougall/computational-thread-art/master/example_images/misc/simpler-patching-path-illustration-dup.png" width="900">


## Path Patching: Name Mover Heads


We'll start with a simple type of path patching - with just one receiver node, which is the final value of the residual stream. We've only discussed receiver nodes being other attention heads so far, but the same priciples hold for any choice of receiver nodes.

<details>
<summary>Question - can you explain the difference between path patching from an attention head to the residual stream, and activation patching on that attention head?</summary>

Activation patching changes the value of that head, and all subsequent layers which depend on that head.

Path patching will answer the question "what if the value written by the head directly to the residual stream was the same as in $x_{new}$, but every non-direct path from this head to the residual stream (i.e. paths going through other heads) the value was the same as it would have been under $x_{orig}$?
</details>

This patching is described at the start of section 3.1 in [the paper](https://arxiv.org/pdf/2211.00593.pdf) (page 5). The 3-step process will look like:

1. Run the model on clean and corrupted input. Cache the head outputs.
2. Run the model on clean input, with the sender head **patched** from the corrupted input, and every other head **frozen** to their values on the clean input. Cache the final value of the residual stream (i.e. `resid_post` in the final layer).
3. Normally we would re-run the model on the clean input and patch in the cached value of the final residual stream, but in this case we don't need to because we can just unembed the final value of the residual stream directly without having to run another forward pass.

Here is an illustration for a 2-layer transformer:

<img src="https://raw.githubusercontent.com/callummcdougall/computational-thread-art/master/example_images/misc/path-patching-residpost-newest.png" width="680">


### Exercise - implement path patching to the final residual stream value

```c
Difficulty: 🟠🟠🟠🟠🟠
Importance: 🟠🟠🟠🟠⚪

You should spend up to 30-45 minutes on this exercise.

Path patching is a very challenging algorithm with many different steps.
```

You should implement path patching from heads to the residual stream, as described above (and in the paper).

This exercise is expected to be challenging, with several moving parts. We've purposefully left it very open-ended, without even giving you a docstring for the function you'll be writing.

Here are a few hints / tips for how to proceed:

* Split your function up into 3 parts (one for each of the steps above), and write each section one at a time.
* You'll need a new hook function: one which performs freezing / patching for step 2 of the algorithm.
* You can reuse a lot of code from your activation patching function.
* When calling `model.run_with_cache`, you can use the keyword argument `names_filter`, which is a function from name to boolean. If you use this argument, your model will only cache activtions with a name which passes this filter (e.g. you can use it like `names_filter = lambda name: name.endswith("q")` to only cache query vectors).

You can also look at the dropdowns to get more hints and guidance (e.g. if you want to start from a function docstring).

You'll know you've succeeded if you can plot the results, and replicate Figure 3(b) from [the paper](https://arxiv.org/pdf/2211.00593.pdf) (at the top of page 6).


<details>
<summary>Click here to get a docstring for the main function.</summary>

```python
def get_path_patch_head_to_final_resid_post(
    model: HookedTransformer,
    patching_metric: Callable,
    new_dataset: IOIDataset = abc_dataset,
    orig_dataset: IOIDataset = ioi_dataset,
    new_cache: Optional[ActivationCache] = abc_cache,
    orig_cache: Optional[ActivationCache] = ioi_cache,
) -> Float[Tensor, "layer head"]:
    '''
    Performs path patching (see algorithm in appendix B of IOI paper), with:

        sender head = (each head, looped through, one at a time)
        receiver node = final value of residual stream

    Returns:
        tensor of metric values for every possible sender head
    '''
    pass
```
</details>

<details>
<summary>Click here to get a docstring for the main function, plus some annotations and function structure.</summary>

```python
def get_path_patch_head_to_final_resid_post(
    model: HookedTransformer,
    patching_metric: Callable,
    new_dataset: IOIDataset = abc_dataset,
    orig_dataset: IOIDataset = ioi_dataset,
    new_cache: Optional[ActivationCache] = abc_cache,
    orig_cache: Optional[ActivationCache] = ioi_cache,
) -> Float[Tensor, "layer head"]:
    '''
    Performs path patching (see algorithm in appendix B of IOI paper), with:

        sender head = (each head, looped through, one at a time)
        receiver node = final value of residual stream

    Returns:
        tensor of metric values for every possible sender head
    '''
    model.reset_hooks()
    results = t.zeros(model.cfg.n_layers, model.cfg.n_heads, device="cuda", dtype=t.float32)

    # ========== Step 1 ==========
    # Gather activations on x_orig and x_new

    # YOUR CODE HERE


    # Using itertools to loop gives us a smoother progress bar (using nested for loops is also fine)
    for (sender_layer, sender_head) in tqdm_notebook(list(itertools.product(
        range(model.cfg.n_layers),
        range(model.cfg.n_heads)
    ))):
        pass

        # ========== Step 2 ==========
        # Run on x_orig, with sender head patched from x_new, every other head frozen

        # YOUR CODE HERE


        # ========== Step 3 ==========
        # Unembed the final residual stream value, to get our patched logits

        # YOUR CODE HERE


        # Save the results
        results[sender_layer, sender_head] = patching_metric(patched_logits)


    return results
```
</details>


```python
# FLAT SOLUTION NOINDENT
# 
def patch_or_freeze_head_vectors(
    orig_head_vector: Float[Tensor, "batch pos head_index d_head"],
    hook: HookPoint, 
    new_cache: ActivationCache,
    orig_cache: ActivationCache,
    head_to_patch: Tuple[int, int], 
) -> Float[Tensor, "batch pos head_index d_head"]:
    '''
    This helps implement step 2 of path patching. We freeze all head outputs (i.e. set them
    to their values in orig_cache), except for head_to_patch (if it's in this layer) which
    we patch with the value from new_cache.

    head_to_patch: tuple of (layer, head)
        we can use hook.layer() to check if the head to patch is in this layer
    '''
    # Setting using ..., otherwise changing orig_head_vector will edit cache value too
    orig_head_vector[...] = orig_cache[hook.name][...]
    if head_to_patch[0] == hook.layer():
        orig_head_vector[:, :, head_to_patch[1]] = new_cache[hook.name][:, :, head_to_patch[1]]
    return orig_head_vector
# FLAT SOLUTION END


def get_path_patch_head_to_final_resid_post(
    model: HookedTransformer,
    patching_metric: Callable,
    new_dataset: IOIDataset = abc_dataset,
    orig_dataset: IOIDataset = ioi_dataset,
    new_cache: Optional[ActivationCache] = abc_cache,
    orig_cache: Optional[ActivationCache] = ioi_cache,
) -> Float[Tensor, "layer head"]:
    pass


if MAIN:
    path_patch_head_to_final_resid_post_eq = get_path_patch_head_to_final_resid_post(model, ioi_metric_2)

```

```python

if MAIN:
    imshow(
        100 * path_patch_head_to_final_resid_post_eq,
        title="Direct effect on logit difference",
        labels={"x":"Head", "y":"Layer", "color": "Logit diff. variation"},
        coloraxis=dict(colorbar_ticksuffix = "%"),
        width=600,
    )

```

<details>
<summary>Solution</summary>


```python
def get_path_patch_head_to_final_resid_post(
    model: HookedTransformer,
    patching_metric: Callable,
    new_dataset: IOIDataset = abc_dataset,
    orig_dataset: IOIDataset = ioi_dataset,
    new_cache: Optional[ActivationCache] = abc_cache,
    orig_cache: Optional[ActivationCache] = ioi_cache,
) -> Float[Tensor, "layer head"]:
    # SOLUTION
    '''
    Performs path patching (see algorithm in appendix B of IOI paper), with:

        sender head = (each head, looped through, one at a time)
        receiver node = final value of residual stream

    Returns:
        tensor of metric values for every possible sender head
    '''
    model.reset_hooks()
    results = t.zeros(model.cfg.n_layers, model.cfg.n_heads, device="cuda", dtype=t.float32)

    resid_post_hook_name = utils.get_act_name("resid_post", model.cfg.n_layers - 1)
    resid_post_name_filter = lambda name: name == resid_post_hook_name


    # ========== Step 1 ==========
    # Gather activations on x_orig and x_new

    # Note the use of names_filter for the run_with_cache function. Using it means we 
    # only cache the things we need (in this case, just attn head outputs).
    z_name_filter = lambda name: name.endswith("z")
    if new_cache is None:
        _, new_cache = model.run_with_cache(
            new_dataset.toks, 
            names_filter=z_name_filter, 
            return_type=None
        )
    if orig_cache is None:
        _, orig_cache = model.run_with_cache(
            orig_dataset.toks, 
            names_filter=z_name_filter, 
            return_type=None
        )


    # Looping over every possible sender head (the receiver is always the final resid_post)
    # Note use of itertools (gives us a smoother progress bar)
    for (sender_layer, sender_head) in tqdm(list(itertools.product(range(model.cfg.n_layers), range(model.cfg.n_heads)))):

        # ========== Step 2 ==========
        # Run on x_orig, with sender head patched from x_new, every other head frozen
        
        hook_fn = partial(
            patch_or_freeze_head_vectors,
            new_cache=new_cache, 
            orig_cache=orig_cache,
            head_to_patch=(sender_layer, sender_head),
        )
        model.add_hook(z_name_filter, hook_fn)
    
        _, patched_cache = model.run_with_cache(
            orig_dataset.toks, 
            names_filter=resid_post_name_filter, 
            return_type=None
        )
        # if (sender_layer, sender_head) == (9, 9):
        #     return patched_cache
        assert set(patched_cache.keys()) == {resid_post_hook_name}

        # ========== Step 3 ==========
        # Unembed the final residual stream value, to get our patched logits

        patched_logits = model.unembed(model.ln_final(patched_cache[resid_post_hook_name]))

        # Save the results
        results[sender_layer, sender_head] = patching_metric(patched_logits)

    return results
```
</details>


What is the interpretation of this plot? How does it compare to the equivalent plot we got from activation patching? (Remember that our metric is defined in a different way, so we should expect a sign difference between the two results.)

<details>
<summary>Some thoughts</summary>

This plot is actually almost identical to the one we got from activation patching (apart from the results being negated, because of the new metric).

This makes sense; the only reason activation patching would do something different to path patching is if the heads writing in the `Mary - John` direction had their outputs used by a later head (because this would be accounted for in activation patching, whereas path patching isolates the direct effect on the residual stream only). Since attention heads' primary purpose is to move information around the model, it's reasonable to guess that this probably isn't happening.

Don't worry though, in the next set of exercises we'll do some more interesting path patching, and we'll get some results which are meaningfully different from our activation patching results.
</details>


## Path Patching: S-Inhibition Heads


In the first section on path patching, we performed a simple kind of patching - from the output of an attention head to the final value of the residual stream. Here we'll do something a bit more interesting, and patch from the output of one head to the input of a later head. The purpose of this is to examine exactly how two heads are composing, and what effect the composed heads have on the model's output.

We got a hint of this in the previous section, where we patched the values of the S-inhibition heads and found that they were important. But this didn't tell us which inputs to these value vectors were important; we had to make educated guesses about this based on our analysis earlier parts of the model. In path patching, we can perform a more precise test to find which heads are important.

The paper's results from path patching are shown in figure 5(b), on page 7.


### Exercise - implement path patching from head to head

```c
Difficulty: 🟠🟠🟠⚪⚪
Importance: 🟠🟠🟠⚪⚪

You should spend up to 20-25 minutes on this exercise.

You'll need a new hook function, but copying code from the previous exercise should make this one easier.
```

You should fill in the function `get_path_patch_head_to_head` below. It takes as arguments a list of receiver nodes (as well as the type of input - keys, queries, or values), and returns a tensor of shape\* `(layer, head)` where each element is the result of running the patching metric on the output of the model, after applying the 3-step path patching algorithm from one of the model's heads to all the receiver heads. You should be able to replicate the paper's results (figure 5(b)).

\**Actually, you don't need to return all layers, because the causal effect from any sender head which is on the same or a later layer than the last of your receiver heads will necessarily be zero.*

If you want a bit more guidance, you can use the dropdown below to see the ways in which this function should be different from your first path patching function (in most ways these functions will be similar, so you can start by copying that function).

<details>
<summary>Differences from first path patching function</summary>

Step 1 is identical in both - gather all the observations.

Step 2 is very similar. The only difference is that you'll be caching a different set of activations (your receiver heads).

In section 3, since your receiver nodes are in the middle of the model rather than at the very end, you will have to run the model again with these nodes patched in rather than just calculating the logit output directly from the patched values of the final residual stream. To do this, you'll have to write a new hook function to patch in the inputs to an attention head (if you haven't done this already).
</details>


```python
# FLAT SOLUTION NOINDENT
# 
def patch_head_input(
    orig_activation: Float[Tensor, "batch pos head_idx d_head"],
    hook: HookPoint,
    patched_cache: ActivationCache,
    head_list: List[Tuple[int, int]],
) -> Float[Tensor, "batch pos head_idx d_head"]:
    '''
    Function which can patch any combination of heads in layers,
    according to the heads in head_list.
    '''
    heads_to_patch = [head for layer, head in head_list if layer == hook.layer()]
    orig_activation[:, :, heads_to_patch] = patched_cache[hook.name][:, :, heads_to_patch]
    return orig_activation
# FLAT SOLUTION END


def get_path_patch_head_to_heads(
    receiver_heads: List[Tuple[int, int]],
    receiver_input: str,
    model: HookedTransformer,
    patching_metric: Callable,
    new_dataset: IOIDataset = abc_dataset,
    orig_dataset: IOIDataset = ioi_dataset,
    new_cache: Optional[ActivationCache] = None,
    orig_cache: Optional[ActivationCache] = None,
) -> Float[Tensor, "layer head"]:
    '''
    Performs path patching (see algorithm in appendix B of IOI paper), with:

        sender head = (each head, looped through, one at a time)
        receiver node = input to a later head (or set of heads)

    The receiver node is specified by receiver_heads and receiver_input.
    Example (for S-inhibition path patching the queries):
        receiver_heads = [(8, 6), (8, 10), (7, 9), (7, 3)],
        receiver_input = "v"

    Returns:
        tensor of metric values for every possible sender head
    '''
    pass


```

```python

if MAIN:
    model.reset_hooks()
    
    s_inhibition_value_path_patching_results = get_path_patch_head_to_heads(
        receiver_heads = [(8, 6), (8, 10), (7, 9), (7, 3)],
        receiver_input = "v",
        model = model,
        patching_metric = ioi_metric_2
    )
    
    imshow(
        100 * s_inhibition_value_path_patching_results,
        title="Direct effect on S-Inhibition Heads' values", 
        labels={"x": "Head", "y": "Layer", "color": "Logit diff.<br>variation"},
        width=600,
        coloraxis=dict(colorbar_ticksuffix = "%"),
    )

```

```python

if MAIN:
    path_patch_head_to_final_resid_post = patching.path_patch(
        model,
        clean_tokens=ioi_dataset.toks,
        corrupted_tokens=abc_dataset.toks,
        clean_cache=ioi_cache,
        corrupted_cache=abc_cache,
        patching_metric=ioi_metric_2,
    
        sender_components="z",
        sender_seq_pos="all",
        receiver_components=[(8, 6, "v"), (8, 10, "v"), (7, 9, "v"), (7, 3, "v")],
        receiver_seq_pos="all",
    
        verbose=True,
    )
    
    
    imshow(
        100 * path_patch_head_to_final_resid_post[:8],
        title="Direct effect on S-Inhibition Heads' values", 
        labels={"x": "Head", "y": "Layer", "color": "Logit diff.<br>variation"},
        width=600,
        coloraxis=dict(colorbar_ticksuffix = "%"),
    )

```

<details>
<summary>Question - what is the interpretation of this plot? </summary>

This plot confirms our earlier observations, that the S-inhibition heads' value vectors are the ones which matter. But it does more, by confirming our hypothesis that the S-inhibition heads' value vectors are supplied to them primarily by the outputs of heads `0.1`, `3.0`, `5.5` and `6.9` (which are the heads found by the paper to be the two most important duplicate token heads and two most important induction heads respectively).
</details>

<details>
<summary>Solution </summary>


</details>




""", unsafe_allow_html=True)


def section_5():

    st.sidebar.markdown(r"""

## Table of Contents

<ul class="contents">
    <li class='margtop'><a class='contents-el' href='#copying-writing-direction-results'>Copying & writing direction results</a></li>
    <li><ul class="contents">
        <li><a class='contents-el' href='#exercise-replicate-writing-direction-results'><b>Exercise</b> - replicate writing direction results</a></li>
        <li><a class='contents-el' href='#exercise-replicate-copying-score-results'><b>Exercise</b> - replicate copying score results</a></li>
    </ul></li>
    <li class='margtop'><a class='contents-el' href='#validation-of-early-heads'>Validation of early heads</a></li>
    <li><ul class="contents">
        <li><a class='contents-el' href='#exercise-perform-head-validation'><b>Exercise</b> - perform head validation</a></li>
    </ul></li>
    <li class='margtop'><a class='contents-el' href='#minimal-circuit'>Minimal Circuit</a></li>
    <li><ul class="contents">
        <li><a class='contents-el' href='#background:-faithfulness-completeness-and-minimality'>Background: faithfulness, completeness, and minimality</a></li>
        <li><a class='contents-el' href='#exercise-constructing-the-minimal-circuit'><b>Exercise</b> - constructing the minimal circuit</a></li>
        <li><a class='contents-el' href='#exercise-calculate-minimality-scores'><b>Exercise</b> - calculate minimality scores</a></li>
</ul></li>""", unsafe_allow_html=True)

    st.markdown(r"""

# 5️⃣ Paper Replication


> ##### Learning objectives
> 
> * Replicate most of the other results from the [IOI paper](https://arxiv.org/abs/2211.00593)
> * Practice more open-ended, less guided coding

This section will be a lot more open-ended and challenging. You'll be given less guidance in the exercises.


## Copying & writing direction results


We'll start this section by replicating the paper's analysis of the **name mover heads** and **negative name mover heads**. Our previous analysis should have pretty much convinced us that these heads are copying / negatively copying our indirect object token, but the results here show this with a bit more rigour.


### Exercise - replicate writing direction results

```c
Difficulty: 🟠🟠🟠🟠⚪
Importance: 🟠🟠⚪⚪⚪

You should spend up to 20-25 minutes on this exercise.

These exercises are much more challenging than they are conceptually important.
```

Let's look at figure 3(c) from the paper. This plots the output of the strongest name mover and negative name mover heads against the attention probabilities for `END` attending to `IO` or `S` (color-coded). 

Some clarifications:
* "Projection" here is being used synonymously with "dot product".
* We're projecting onto the name embedding, i.e. the embedding vector for the token which is being paid attention to. This is not the same as the logit diff (which we got by projecting the heads' output onto the difference between the unembedding vectors for `IO` and `S`).
    * We're doing this because the question we're trying to answer is *"does the attention head copy (or anti-copy) the names which it pays attention to?"*



You should write code to replicate the paper's results in the cells below. Given four 1D tensors storing the results for a particular head (i.e. the projections and attention probabilities, for the `IO` and `S` tokens respectively), we've given you code to generate a plot which looks like the one in the paper. Again, you'll know that your code has worked if you can get results that resemble those in the paper.


```python
def scatter_embedding_vs_attn(
    attn_from_end_to_io: Float[Tensor, "batch"],
    attn_from_end_to_s: Float[Tensor, "batch"],
    projection_in_io_dir: Float[Tensor, "batch"],
    projection_in_s_dir: Float[Tensor, "batch"],
    layer: int,
    head: int
):
    scatter(
        x=t.concat([attn_from_end_to_io, attn_from_end_to_s], dim=0),
        y=t.concat([projection_in_io_dir, projection_in_s_dir], dim=0),
        color=["IO"] * N + ["S"] * N,
        title=f"Projection of the output of {layer}.{head} along the name<br>embedding vs attention probability on name",
        title_x=0.5,
        labels={"x": "Attn prob on name", "y": "Dot w Name Embed", "color": "Name type"},
        color_discrete_sequence=["#72FF64", "#C9A5F7"],
        width=650
    )

```

```python
def calculate_and_show_scatter_embedding_vs_attn(
    layer: int,
    head: int,
    cache: ActivationCache = ioi_cache,
    dataset: IOIDataset = ioi_dataset,
) -> None:
    '''
    Creates and plots a figure equivalent to 3(c) in the paper.

    This should involve computing the four 1D tensors:
        attn_from_end_to_io
        attn_from_end_to_s
        projection_in_io_dir
        projection_in_s_dir
    and then calling the scatter_embedding_vs_attn function.
    '''
    pass


if MAIN:
    nmh = (9, 9)
    calculate_and_show_scatter_embedding_vs_attn(*nmh)
    
    nnmh = (11, 10)
    calculate_and_show_scatter_embedding_vs_attn(*nnmh)

```

<details>
<summary>Solution</summary>


Note the copious type annotations - this is just a personal preference and I've been told that other people don't like this style of coding as much! However, I'd strongly recommend it, because it helps you keep track of things and can massively improve your efficiency.


```python
def get_path_patch_head_to_heads(
    receiver_heads: List[Tuple[int, int]],
    receiver_input: str,
    model: HookedTransformer,
    patching_metric: Callable,
    new_dataset: IOIDataset = abc_dataset,
    orig_dataset: IOIDataset = ioi_dataset,
    new_cache: Optional[ActivationCache] = None,
    orig_cache: Optional[ActivationCache] = None,
) -> Float[Tensor, "layer head"]:
    '''
    Performs path patching (see algorithm in appendix B of IOI paper), with:

        sender head = (each head, looped through, one at a time)
        receiver node = input to a later head (or set of heads)

    The receiver node is specified by receiver_heads and receiver_input.
    Example (for S-inhibition path patching the queries):
        receiver_heads = [(8, 6), (8, 10), (7, 9), (7, 3)],
        receiver_input = "v"

    Returns:
        tensor of metric values for every possible sender head
    '''
    # SOLUTION
    model.reset_hooks()

    assert receiver_input in ("k", "q", "v")
    receiver_layers = set(next(zip(*receiver_heads)))
    receiver_hook_names = [utils.get_act_name(receiver_input, layer) for layer in receiver_layers]
    receiver_hook_names_filter = lambda name: name in receiver_hook_names

    results = t.zeros(max(receiver_layers), model.cfg.n_heads, device="cuda", dtype=t.float32)
    
    # ========== Step 1 ==========
    # Gather activations on x_orig and x_new

    # Note the use of names_filter for the run_with_cache function. Using it means we 
    # only cache the things we need (in this case, just attn head outputs).
    z_name_filter = lambda name: name.endswith("z")
    if new_cache is None:
        _, new_cache = model.run_with_cache(
            new_dataset.toks, 
            names_filter=z_name_filter, 
            return_type=None
        )
    if orig_cache is None:
        _, orig_cache = model.run_with_cache(
            orig_dataset.toks, 
            names_filter=z_name_filter, 
            return_type=None
        )

    # Note, the sender layer will always be before the final receiver layer, otherwise there will
    # be no causal effect from sender -> receiver. So we only need to loop this far.
    for (sender_layer, sender_head) in tqdm(list(itertools.product(
        range(max(receiver_layers)),
        range(model.cfg.n_heads)
    ))):

        # ========== Step 2 ==========
        # Run on x_orig, with sender head patched from x_new, every other head frozen

        hook_fn = partial(
            patch_or_freeze_head_vectors,
            new_cache=new_cache, 
            orig_cache=orig_cache,
            head_to_patch=(sender_layer, sender_head),
        )
        model.add_hook(z_name_filter, hook_fn) #, level=1)
        
        _, patched_cache = model.run_with_cache(
            orig_dataset.toks, 
            names_filter=receiver_hook_names_filter,  
            return_type=None
        )
        # model.reset_hooks(including_permanent=True)
        assert set(patched_cache.keys()) == set(receiver_hook_names)

        # ========== Step 3 ==========
        # Run on x_orig, patching in the receiver node(s) from the previously cached value
        
        hook_fn = partial(
            patch_head_input, 
            patched_cache=patched_cache, 
            head_list=receiver_heads,
        )
        patched_logits = model.run_with_hooks(
            orig_dataset.toks,
            fwd_hooks = [(receiver_hook_names_filter, hook_fn)], 
            return_type="logits"
        )

        # Save the results
        results[sender_layer, sender_head] = patching_metric(patched_logits)

    return results

def calculate_and_show_scatter_embedding_vs_attn(
    layer: int,
    head: int,
    cache: ActivationCache = ioi_cache,
    dataset: IOIDataset = ioi_dataset,
) -> None:
    '''
    Creates and plots a figure equivalent to 3(c) in the paper.

    This should involve computing the four 1D tensors:
        attn_from_end_to_io
        attn_from_end_to_s
        projection_in_io_dir
        projection_in_s_dir
    and then calling the scatter_embedding_vs_attn function.
    '''
    # SOLUTION
    # Get the value written to the residual stream at the end token by this head
    z: Float[Tensor, "batch seq d_head"] = cache[utils.get_act_name("z", layer)][:, :, head]
    N = z.size(0)
    output: Float[Tensor, "batch seq d_model"] = z @ model.W_O[layer, head]
    output_on_end_token: Float[Tensor, "batch d_model"] = output[t.arange(N), dataset.word_idx["end"]]

    # Get the directions we'll be projecting onto
    io_unembedding: Float[Tensor, "batch d_model"] = model.W_U.T[dataset.io_tokenIDs]
    s_unembedding: Float[Tensor, "batch d_model"] = model.W_U.T[dataset.s_tokenIDs]

    # Get the value of projections, by multiplying and summing over the d_model dimension
    projection_in_io_dir: Float[Tensor, "batch"] = (output_on_end_token * io_unembedding).sum(-1)
    projection_in_s_dir: Float[Tensor, "batch"] = (output_on_end_token * s_unembedding).sum(-1)

    # Get attention probs, and index to get the probabilities from END -> IO / S
    attn_probs: Float[Tensor, "batch q k"] = cache["pattern", layer][:, head]
    attn_from_end_to_io = attn_probs[t.arange(N), dataset.word_idx["end"], dataset.word_idx["IO"]]
    attn_from_end_to_s = attn_probs[t.arange(N), dataset.word_idx["end"], dataset.word_idx["S1"]]

    # Show scatter plot
    scatter_embedding_vs_attn(
        attn_from_end_to_io, 
        attn_from_end_to_s, 
        projection_in_io_dir, 
        projection_in_s_dir, 
        layer, 
        head
    )
```
</details>

<details>
<summary>Question - what is the interpretation of this plot in the paper?</summary>

For head `9.9`, Both the `S` and `IO` tokens exhibit a positive correlation between their contribution to logit difference and the attention probability on their name. This suggests the head is just copying names it attends to from the name to the `END` token. We can see that it is paying more attention to the `IO` token and less on `S`, which is what we expect (thanks to Q-composition with the S-inhibition heads).

The same is true for the negative name mover head `11.10`, only it works in the opposite direction (actively suppressing the logit score for the names it attends to). Note, it's important that we observe this negative correlation, because this shows us that the head really is anti-copying the `IO` token (rather than just copying the `S` token).
</details>


### Exercise - replicate copying score results

```c
Difficulty: 🟠🟠🟠🟠🟠
Importance: 🟠🟠⚪⚪⚪

You should spend up to 30-40 minutes on this exercise.

These exercises are much more challenging than they are conceptually important.
```

Now let's do a different kind of test of the name mover heads' copying, by looking directly at the OV circuits.

From page 6 of the paper:

> To check that the Name Mover Heads copy names generally, we studied what values are written via the heads’ OV matrix. Specifically, we first obtained the state of the residual stream at the position of each name token after the first MLP layer. Then, we multiplied this by the OV matrix of a Name Mover Head (simulating what would happen if the head attended perfectly to that token), multiplied by the unembedding matrix, and applied the final layer norm to obtain logit probabilities. We compute the proportion of samples that contain the input name token in the top 5 logits (N = 1000) and call this the copy score. All three Name Mover Heads have a copy score above 95%, compared to less than 20% for an average head.
>
> Negative Name Mover Heads ... have a large negative copy score–the copy score calculated with the negative of the OV matrix (98% compared to 12% for an average head).

Note the similarity between their method and how we studied copying in induction heads, during an earlier set of exercises. However, there are differences (e.g. we're only looking at whether the head copies names, rather than whether it copies tokens in general).


You should replicate these results by completing the `get_copying_scores` function below.

You could do this by indexing from the `ioi_cache`, but a much more principled alternative would be to embed all the names in the `NAMES` list and apply operations like MLPs, layernorms and OV matrices manually. This is what the solutions do.

A few notes:

* You can use `model.to_tokens` to convert the names to tokens. Remember to use `prepend_bos=False`, since you just want the tokens of names so you can embed them. Note that this function will treat the list of names as a batch of single-token inputs, which works fine for our purposes.
* You can apply MLPs and layernorms as functions, by just indexing the model's blocks (e.g. use `model.blocks[i].mlp` or `model.blocks[j].ln1` as a function). Remember that `ln1` is the layernorm that comes before attention, and `ln2` comes before the MLP.

Also, you shouldn't expect to get exactly the same results as the paper (because some parts of this experiment have been set up very slightly different), although you probably shouldn't be off by more than 10%.


```python
def get_copying_scores(
    model: HookedTransformer,
    k: int = 5,
    names: list = NAMES
) -> Float[Tensor, "2 layer head"]:
    '''
    Gets copying scores (both positive and negative) as described in page 6 of the IOI paper, for every (layer, head) pair in the model.
    
    Returns these in a 3D tensor (the first dimension is for positive vs negative).
    '''
    pass


```

```python

if MAIN:
    copying_results = get_copying_scores(model)
    
    imshow(
        copying_results, 
        facet_col=0, 
        facet_labels=["Positive copying scores", "Negative copying scores"],
        title="Copying scores of attention heads' OV circuits",
        width=800
    )

```

```python

if MAIN:
    heads = {"name mover": [(9, 9), (10, 0), (9, 6)], "negative name mover": [(10, 7), (11, 10)]}
    
    for i, name in enumerate(["name mover", "negative name mover"]):
        make_table(
            title=f"Copying Scores ({name} heads)",
            colnames=["Head", "Score"],
            cols=[
                list(map(str, heads[name])) + ["[dark_orange bold]Average"],
                [f"{copying_results[i, layer, head]:.2%}" for (layer, head) in heads[name]] + [f"[dark_orange bold]{copying_results[i].mean():.2%}"]
            ]
        )

```

<details>
<summary>Solution</summary>


```python
def get_copying_scores(
    model: HookedTransformer,
    k: int = 5,
    names: list = NAMES
) -> Float[Tensor, "2 layer head"]:
    '''
    Gets copying scores (both positive and negative) as described in page 6 of the IOI paper, for every (layer, head) pair in the model.
    
    Returns these in a 3D tensor (the first dimension is for positive vs negative).
    '''
    # SOLUTION
    results = t.zeros((2, model.cfg.n_layers, model.cfg.n_heads), device="cuda")

    # Define components from our model (for typechecking, and cleaner code)
    embed: Embed = model.embed
    mlp0: MLP = model.blocks[0].mlp
    ln0: LayerNorm = model.blocks[0].ln2
    unembed: Unembed = model.unembed
    ln_final: LayerNorm = model.ln_final

    # Get embeddings for the names in our list
    name_tokens: Int[Tensor, "batch 1"] = model.to_tokens(names, prepend_bos=False)
    name_embeddings: Int[Tensor, "batch 1 d_model"] = embed(name_tokens)
    
    # Get residual stream after applying MLP
    resid_after_mlp1 = name_embeddings + mlp0(ln0(name_embeddings))

    # Loop over all (layer, head) pairs
    for layer in range(model.cfg.n_layers):
        for head in range(model.cfg.n_heads):

            # Get W_OV matrix
            W_OV = model.W_V[layer, head] @ model.W_O[layer, head]

            # Get residual stream after applying W_OV or -W_OV respectively
            # (note, because of bias b_U, it matters that we do sign flip here, not later)
            resid_after_OV_pos = resid_after_mlp1 @ W_OV
            resid_after_OV_neg = resid_after_mlp1 @ -W_OV

            # Get logits from value of residual stream
            logits_pos: Float[Tensor, "batch d_vocab"] = unembed(ln_final(resid_after_OV_pos)).squeeze()
            logits_neg: Float[Tensor, "batch d_vocab"] = unembed(ln_final(resid_after_OV_neg)).squeeze()

            # Check how many are in top k
            topk_logits: Int[Tensor, "batch k"] = t.topk(logits_pos, dim=-1, k=k).indices
            in_topk = (topk_logits == name_tokens).any(-1)
            # Check how many are in bottom k
            bottomk_logits: Int[Tensor, "batch k"] = t.topk(logits_neg, dim=-1, k=k).indices
            in_bottomk = (bottomk_logits == name_tokens).any(-1)

            # Fill in results
            results[:, layer, head] = t.tensor([in_topk.float().mean(), in_bottomk.float().mean()])

    return results
```
</details>


## Validation of early heads


There are three different kinds of heads which appear early in the circuit, which can be validated by looking at their attention patterns on simple random sequences of tokens. Can you figure out which three types these are, and how to validate them in this way?

<details>
<summary>Answer</summary>

Previous token heads, induction heads, and duplicate token heads.

We can validate them all at the same time, using sequences of `n` random tokens followed by those same `n` random tokens repeated. This works as follows:

* Prev token heads, by measuring the attention patterns with an offset of one (i.e. one below the diagonal).
* Induction heads, by measuring the attention patterns with an offset of `n-1` (i.e. the second instance of a token paying attention to the token after its first instance).
* Duplicate token heads, by measuring the attention patterns with an offset of `n` (i.e. a token paying attention to its previous instance).

In all three cases, if heads score close to 1 on these metrics, it's strong evidence that they are working as this type of head.

Note, it's a leaky abstraction to say things like "head X is an induction head", since we're only observing it on a certain distribution. For instance, it's not clear what the role of induction heads and duplicate token heads is when there are no duplicates (they could in theory do something completely different).
</details>


### Exercise - perform head validation

```c
Difficulty: 🟠🟠🟠⚪⚪
Importance: 🟠🟠🟠⚪⚪

You should spend up to 20-30 minutes on this exercise.

Understanding how to identify certain types of heads by their characteristic attention patterns is important.
```

Once you've read the answer in the dropdown above, you should perform this validation. The result should be a replication of Figure 18 in the paper (don't look at this figure until you've attempted the question above, because it will give away the answer!). 

We've provided a template for this function. Note use of `typing.Literal`, which is how we indicate that the argument should be one of the following options.


```python

if MAIN:
    model.reset_hooks()
    
    # FLAT SOLUTION NOINDENT
    # 
def generate_repeated_tokens(
    model: HookedTransformer, 
    seq_len: int, 
    batch: int = 1
) -> Float[Tensor, "batch 2*seq_len"]:
    '''
    Generates a sequence of repeated random tokens (no start token).
    '''
    rep_tokens_half = t.randint(0, model.cfg.d_vocab, (batch, seq_len), dtype=t.int64)
    rep_tokens = t.cat([rep_tokens_half, rep_tokens_half], dim=-1).to(device)
    return rep_tokens
# FLAT SOLUTION END


def get_attn_scores(
    model: HookedTransformer, 
    seq_len: int, 
    batch: int, 
    head_type: Literal["duplicate", "prev", "induction"]
):
    '''
    Returns attention scores for sequence of duplicated tokens, for every head.
    '''
    pass

def plot_early_head_validation_results(seq_len: int = 50, batch: int = 50):
    '''
    Produces a plot that looks like Figure 18 in the paper.
    '''
    head_types = ["duplicate", "prev", "induction"]

    results = t.stack([
        get_attn_scores(model, seq_len, batch, head_type=head_type)
        for head_type in head_types
    ])

    imshow(
        results,
        facet_col=0,
        facet_labels=[
            f"{head_type.capitalize()} token attention prob.<br>on sequences of random tokens"
            for head_type in head_types
        ],
        labels={"x": "Head", "y": "Layer"},
        width=1300,
    )



if MAIN:
    plot_early_head_validation_results()

```

<details>
<summary>Solution</summary>


```python
def get_attn_scores(
    model: HookedTransformer, 
    seq_len: int, 
    batch: int, 
    head_type: Literal["duplicate", "prev", "induction"]
):
    '''
    Returns attention scores for sequence of duplicated tokens, for every head.
    '''
    # SOLUTION
    rep_tokens = generate_repeated_tokens(model, seq_len, batch)

    _, cache = model.run_with_cache(
        rep_tokens,
        return_type=None,
        names_filter=lambda name: name.endswith("pattern")
    )

    # Get the right indices for the attention scores
    
    if head_type == "duplicate":
        src_indices = range(seq_len)
        dest_indices = range(seq_len, 2 * seq_len)
    elif head_type == "prev":
        src_indices = range(seq_len)
        dest_indices = range(1, seq_len + 1)
    elif head_type == "induction": 
        dest_indices = range(seq_len, 2 * seq_len)
        src_indices = range(1, seq_len + 1)
    else:
        raise ValueError(f"Unknown head type {head_type}")

    results = t.zeros(model.cfg.n_layers, model.cfg.n_heads, device="cuda", dtype=t.float32)
    for layer in range(model.cfg.n_layers):
        for head in range(model.cfg.n_heads):
            attn_scores: Float[Tensor, "batch head dest src"] = cache["pattern", layer]
            avg_attn_on_duplicates = attn_scores[:, head, dest_indices, src_indices].mean().item()
            results[layer, head] = avg_attn_on_duplicates

    return results
```
</details>


Note - these figures suggest that it would be a useful bit of infrastructure to have a "wiki" for the heads of a model, giving their scores according to some metrics re head functions, like the ones we've seen here. HookedTransformer makes this pretty easy to make, as just changing the name input to `HookedTransformer.from_pretrained` gives a different model but in the same architecture, so the same code should work. If you want to make this, I'd love to see it!

As a proof of concept, [I made a mosaic of all induction heads across the 40 models then in HookedTransformer](https://www.neelnanda.io/mosaic).


## Minimal Circuit


### Background: faithfulness, completeness, and minimality


The authors developed three criteria for validating their circuit explanations: faithfulness, completeness and minimality. They are defined as follows:

* **Faithful** = the circuit can perform as well as the whole model
* **Complete** = the circuit contains all nodes used to perform the task
* **Minimal** = the circuit doesn't contain nodes irrelevant to the task

If all three criteria are met, then the circuit is considered a reliable explanation for model behaviour.

Exercise - can you understand why each of these criteria is important? For each pair of criteria, is it possible for a circuit to meet them both but fail the third (and if yes, can you give examples?).

<details>
<summary>Answer</summary>

The naive circuit (containing the entire model) is trivially faithful and complete, but obviously not minimal. In general, the problem with non-minimal circuits is that they may not be mechanistically understandable, which defeats the purpose of this kind of circuit analysis.

Completeness obviously implies faithfulness, because if a node isn't involved in the task, then it can't improve the model's performance on that task. 

You might initially think faithfulness implies completeness, but this actually isn't true. Backup name mover heads illustrate this point. They are used in the task, and without understanding the role they play you'll have an incorrect model of reality (e.g. you'll think ablating the name mover heads would destroy performance, which turns out not to be true). So if you define a circuit that doesn't contain backup name mover heads then it will be faithful (the backup name mover heads won't be used) but not complete.

Summary:

* **Faithful & complete, not minimal** = possible (example: naive circuit)
* **Faithful & minimal, not complete** = possible (example: circuit missing backup name mover heads)
* **Complete & minimal, not faithful** = impossible (since completeness implies faithfulness)

In the paper, the authors formalise these concepts. Faithfulness is equivalent to $|F(C) - F(M)|$ being small (where $C$ is our circuit, $M$ is the model, and $F$ is our performance metric function), and completeness is equivalent to $|F(C\backslash K) - F(M\backslash K)|$ being small **for any subset $K \subset C$** (including when $K$ is the empty set, showing that completeness implies faithfulness). Can you see how our circuit missing backup name mover heads violates this condition?

<details>
<summary>Answer</summary>

It violates the condition when $K$ is the set of name mover heads. $C \backslash K$ performs worse than $M \backslash K$, because the latter contains backup name mover heads while the former has lost its name mover heads ***and*** backup name mover heads.
</details>
</details>


Now that we've analysed most components of the circuit and we have a rough idea of how they work, the next step is to ablate everything except those core components and verify that the model still performs well.

This ablation is pretty massive - we're ablating everything except for the output of each of our key attention heads (e.g. duplicate token heads or S-inhibition heads) at a single sequence position (e.g. for the DTHs this is the `S2` token, and for SIHs this is the `end` token). Given that our core circuit has 26 heads in total, and our sequences have length around 20 on average, this means we're ablating all but $(26 / 144) / 20 \approx 1\%$ of our attention heads' output (and the number of possible paths through the model is reduced by ***much*** more than this).


How do we ablate? We could use zero-ablation, but this actually has some non-obvious problems. To explain why intuitively, heads might be "expecting" non-zero input, and setting the input to zero is essentially an arbitrary choice which takes it off distribution. You can think of this as adding a bias term to this head, which might mess up subsequent computation and lead to noisy results. We could also use mean-ablation (i.e. set a head's output to its average output over `ioi_dataset`), but the problem here is that taking the mean over this dataset might contain relevant information for solving the IOI task. For example the `is_duplicated` flag which gets written to `S2` will be present for all sequences, so averaging won't remove this information.

Can you think of a way to solve this problem? After you've considered this, you can use the dropdown below to see how the authors handled this.

<details>
<summary>Solution</summary>

We ablate with the mean of the ABC dataset rather than the IOI dataset. This removes the problem of averages still containing relevant information from solving the IOI task.

</details>

One other complication - the sentences have different templates, and the positions of tokens like `S` and `IO` are not consistent across these templates (we avoided this problem in previous exercises by choosing a very small set of sentences, where all the important tokens had the same indices). An example of two templates with different positions:

```
"Then, [B] and [A] had a long argument and after that [B] said to [A]"
"After the lunch [B] and [A] went to the [PLACE], and [B] gave a [OBJECT] to [A]"
```

Can you guess what the authors did to solve this problem?

<details>
<summary>Answer</summary>

They took the mean over each template rather than over the whole dataset, and used these values to ablate with.

In other words, when they performed ablation by patching in the output of a head (which has shape `(batch, seq, d_model)`), the value patched into the `(i, j, k)`-th element of this tensor would be the average value of the `k`-th element of the vector at sequence position `j`, for all sentences with the same template as the `i`-th sentence in the batch.
</details>


### Exercise - constructing the minimal circuit

```c
Difficulty: 🟠🟠🟠🟠🟠
Importance: 🟠🟠⚪⚪⚪

This exercise is expected to take a long time; at least an hour. It is probably the most challenging exercise in this notebook.
```


You now have enough information to perform ablation on your model, to get the minimal circuit. Below, you can try to implement this yourself.

This exercise is very technically challenging, so you're welcome to skip it if it doesn't seem interesting to you. However, I recommend you have a read of the solution, to understand the rough contours of how this ablation works.

If you want to attempt this task, then you can start with the code below. We define two dictionaries, one mapping head types to the heads in the model which are of that type, and the other mapping head types to the sequence positions which we *won't* be ablating for those types of head.


```python

if MAIN:
    CIRCUIT = {
        "name mover": [(9, 9), (10, 0), (9, 6)],
        "backup name mover": [(10, 10), (10, 6), (10, 2), (10, 1), (11, 2), (9, 7), (9, 0), (11, 9)],
        "negative name mover": [(10, 7), (11, 10)],
        "s2 inhibition": [(7, 3), (7, 9), (8, 6), (8, 10)],
        "induction": [(5, 5), (5, 8), (5, 9), (6, 9)],
        "duplicate token": [(0, 1), (0, 10), (3, 0)],
        "previous token": [(2, 2), (4, 11)],
    }
    
    SEQ_POS_TO_KEEP = {
        "name mover": "end",
        "backup name mover": "end",
        "negative name mover": "end",
        "s2 inhibition": "end",
        "induction": "S2",
        "duplicate token": "S2",
        "previous token": "S1+1",
    }

```

To be clear, the things that we'll be mean-ablating are:

* Every head not in the `CIRCUIT` dict
* Every sequence position for the heads in `CIRCUIT` dict, except for the sequence positions given by the `SEQ_POS_TO_KEEP` dict

And we'll be mean-ablating by replacing a head's output with the mean output for `abc_dataset`, over all sentences with the same template as the sentence in the batch. You can access the templates for a dataset using the `dataset.groups` attribute, which returns a list of tensors (each one containing the indices of sequences in the batch sharing the same template).


Now, you can try and complete the following function, which should add a ***permanent hook*** to perform this ablation whenever the model is run on the `ioi_dataset` (note that this hook will only make sense if the model is run on this dataset, so we should reset hooks if we run it on a different dataset). 

Permanent hooks are a useful feature of transformerlens. They behave just like regular hooks, except they aren't removed when you run the model (e.g. using `model.run_with_cache` or `model.run_with_hooks`). The only way to remove them is with:

```python
model.reset_hooks(including_permanent=True)
```

You can add permanent hooks as follows:

```python
model.add_hook(hook_name, hook_fn, is_permanent=True)
```

where `hook_name` can be a string or a filter function mapping strings to booleans.


```python
# FLAT SOLUTION NOINDENT
# 
def get_heads_and_posns_to_keep(
    means_dataset: IOIDataset,
    model: HookedTransformer,
    circuit: Dict[str, List[Tuple[int, int]]],
    seq_pos_to_keep: Dict[str, str],
) -> Dict[int, Bool[Tensor, "batch seq head"]]:
    '''
    Returns a dictionary mapping layers to a boolean mask giving the indices of the 
    z output which *shouldn't* be mean-ablated.

    The output of this function will be used for the hook function that does ablation.
    '''
    heads_and_posns_to_keep = {}
    batch, seq, n_heads = len(means_dataset), means_dataset.max_len, model.cfg.n_heads

    for layer in range(model.cfg.n_layers):

        mask = t.zeros(size=(batch, seq, n_heads))

        for (head_type, head_list) in circuit.items():
            seq_pos = seq_pos_to_keep[head_type]
            indices = means_dataset.word_idx[seq_pos]
            for (layer_idx, head_idx) in head_list:
                if layer_idx == layer:
                    mask[:, indices, head_idx] = 1

        heads_and_posns_to_keep[layer] = mask.bool()

    return heads_and_posns_to_keep

    
def hook_fn_mask_z(
    z: Float[Tensor, "batch seq head d_head"],
    hook: HookPoint,
    heads_and_posns_to_keep: Dict[int, Bool[Tensor, "batch seq head"]],
    means: Float[Tensor, "layer batch seq head d_head"],
) -> Float[Tensor, "batch seq head d_head"]:
    '''
    Hook function which masks the z output of a transformer head.

    heads_and_posns_to_keep
        Dict created with the get_heads_and_posns_to_keep function. This tells
        us where to mask.

    means
        Tensor of mean z values of the means_dataset over each group of prompts
        with the same template. This tells us what values to mask with.
    '''
    # Get the mask for this layer, and add d_head=1 dimension so it broadcasts correctly
    mask_for_this_layer = heads_and_posns_to_keep[hook.layer()].unsqueeze(-1).to(z.device)

    # Set z values to the mean 
    z = t.where(mask_for_this_layer, z, means[hook.layer()])

    return z


def compute_means_by_template(
    means_dataset: IOIDataset, 
    model: HookedTransformer
) -> Float[Tensor, "layer batch seq head_idx d_head"]:
    '''
    Returns the mean of each head's output over the means dataset. This mean is
    computed separately for each group of prompts with the same template (these
    are given by means_dataset.groups).
    '''
    # Cache the outputs of every head
    _, means_cache = model.run_with_cache(
        means_dataset.toks.long(),
        return_type=None,
        names_filter=lambda name: name.endswith("z"),
    )
    # Create tensor to store means
    n_layers, n_heads, d_head = model.cfg.n_layers, model.cfg.n_heads, model.cfg.d_head
    batch, seq_len = len(means_dataset), means_dataset.max_len
    means = t.zeros(size=(n_layers, batch, seq_len, n_heads, d_head), device=model.cfg.device)

    # Get set of different templates for this data
    for layer in range(model.cfg.n_layers):
        z_for_this_layer: Float[Tensor, "batch seq head d_head"] = means_cache[utils.get_act_name("z", layer)]
        for template_group in means_dataset.groups:
            z_for_this_template = z_for_this_layer[template_group]
            z_means_for_this_template = einops.reduce(z_for_this_template, "batch seq head d_head -> seq head d_head", "mean")
            means[layer, template_group] = z_means_for_this_template

    return means


def add_mean_ablation_hook(
    model: HookedTransformer, 
    means_dataset: IOIDataset, 
    circuit: Dict[str, List[Tuple[int, int]]] = CIRCUIT,
    seq_pos_to_keep: Dict[str, str] = SEQ_POS_TO_KEEP,
    is_permanent: bool = True,
) -> HookedTransformer:
    '''
    Adds a permanent hook to the model, which ablates according to the circuit and 
    seq_pos_to_keep dictionaries.

    In other words, when the model is run on ioi_dataset, every head's output will 
    be replaced with the mean over means_dataset for sequences with the same template,
    except for a subset of heads and sequence positions as specified by the circuit
    and seq_pos_to_keep dicts.
    '''
    
    model.reset_hooks(including_permanent=True)

    # Compute the mean of each head's output on the ABC dataset, grouped by template
    means = compute_means_by_template(means_dataset, model)
    
    # Convert this into a boolean map
    heads_and_posns_to_keep = get_heads_and_posns_to_keep(means_dataset, model, circuit, seq_pos_to_keep)

    # Get a hook function which will patch in the mean z values for each head, at 
    # all positions which aren't important for the circuit
    hook_fn = partial(
        hook_fn_mask_z, 
        heads_and_posns_to_keep=heads_and_posns_to_keep, 
        means=means
    )

    # Apply hook
    model.add_hook(lambda name: name.endswith("z"), hook_fn, is_permanent=is_permanent)

    return model
# FLAT SOLUTION END

```

To test whether your function works, you can use the function provided to you, and see if the logit difference from your implementation of the circuit matches this one:


```python
import part3_indirect_object_identification.ioi_circuit_extraction as ioi_circuit_extraction


if MAIN:
    model = ioi_circuit_extraction.add_mean_ablation_hook(model, means_dataset=abc_dataset, circuit=CIRCUIT, seq_pos_to_keep=SEQ_POS_TO_KEEP)
    
    ioi_logits_minimal = model(ioi_dataset.toks)
    
    print(f"Average logit difference (IOI dataset, using entire model): {logits_to_ave_logit_diff_2(ioi_logits_original):.4f}")
    print(f"Average logit difference (IOI dataset, only using circuit): {logits_to_ave_logit_diff_2(ioi_logits_minimal):.4f}")

```

```python

if MAIN:
    model = add_mean_ablation_hook(model, means_dataset=abc_dataset, circuit=CIRCUIT, seq_pos_to_keep=SEQ_POS_TO_KEEP)
    
    ioi_logits_minimal = model(ioi_dataset.toks)
    
    print(f"Average logit difference (IOI dataset, using entire model): {logits_to_ave_logit_diff_2(ioi_logits_original):.4f}")
    print(f"Average logit difference (IOI dataset, only using circuit): {logits_to_ave_logit_diff_2(ioi_logits_minimal):.4f}")

```

You should find that the logit difference only drops by a small amount, and is still high enough to represent a high likelihood ratio favouring the IO token over S.


<details>
<summary>Hint (docstrings of some functions which will be useful for your main function)</summary>

```python
def compute_means_by_template(
    means_dataset: IOIDataset, 
    model: HookedTransformer
) -> Float[Tensor, "layer batch seq head_idx d_head"]:
    '''
    Returns the mean of each head's output over the means dataset. This mean is
    computed separately for each group of prompts with the same template (these
    are given by means_dataset.groups).
    '''
    pass


def get_heads_and_posns_to_keep(
    means_dataset: IOIDataset,
    model: HookedTransformer,
    circuit: Dict[str, List[Tuple[int, int]]],
    seq_pos_to_keep: Dict[str, str],
) -> Dict[int, Bool[Tensor, "batch seq head"]]:
    '''
    Returns a dictionary mapping layers to a boolean mask giving the indices of the 
    z output which *shouldn't* be mean-ablated.

    The output of this function will be used for the hook function that does ablation.
    '''
    pass


def hook_fn_mask_z(
    z: Float[Tensor, "batch seq head d_head"],
    hook: HookPoint,
    heads_and_posns_to_keep: Dict[int, Bool[Tensor, "batch seq head"]],
    means: Float[Tensor, "layer batch seq head d_head"],
) -> Float[Tensor, "batch seq head d_head"]:
    '''
    Hook function which masks the z output of a transformer head.

    heads_and_posns_to_keep
        Dict created with the get_heads_and_posns_to_keep function. This tells
        us where to mask.

    means
        Tensor of mean z values of the means_dataset over each group of prompts
        with the same template. This tells us what values to mask with.
    '''
    pass
```

Once you fill in these three functions, completing the main function is simple. It should:

* Use `compute_means_by_template` to get the means
* Use `get_heads_and_posns_to_keep` to get the boolean mask
* Apply `functools.partial` to `hook_fn_mask_z`, using the outputs of the 2 previous functions, to get your hook function which performs the mean ablation
* Add this hook function to your model, as a permanent hook

</details>


<details>
<summary>Solution</summary>

```python
def get_heads_and_posns_to_keep(
    means_dataset: IOIDataset,
    model: HookedTransformer,
    circuit: Dict[str, List[Tuple[int, int]]],
    seq_pos_to_keep: Dict[str, str],
) -> Dict[int, Bool[Tensor, "batch seq head"]]:
    '''
    Returns a dictionary mapping layers to a boolean mask giving the indices of the 
    z output which *shouldn't* be mean-ablated.

    The output of this function will be used for the hook function that does ablation.
    '''
    heads_and_posns_to_keep = {}
    batch, seq, n_heads = len(means_dataset), means_dataset.max_len, model.cfg.n_heads

    for layer in range(model.cfg.n_layers):

        mask = t.zeros(size=(batch, seq, n_heads))

        for (head_type, head_list) in circuit.items():
            seq_pos = seq_pos_to_keep[head_type]
            indices = means_dataset.word_idx[seq_pos]
            for (layer_idx, head_idx) in head_list:
                if layer_idx == layer:
                    mask[:, indices, head_idx] = 1

        heads_and_posns_to_keep[layer] = mask.bool()

    return heads_and_posns_to_keep

    
def hook_fn_mask_z(
    z: Float[Tensor, "batch seq head d_head"],
    hook: HookPoint,
    heads_and_posns_to_keep: Dict[int, Bool[Tensor, "batch seq head"]],
    means: Float[Tensor, "layer batch seq head d_head"],
) -> Float[Tensor, "batch seq head d_head"]:
    '''
    Hook function which masks the z output of a transformer head.

    heads_and_posns_to_keep
        Dict created with the get_heads_and_posns_to_keep function. This tells
        us where to mask.

    means
        Tensor of mean z values of the means_dataset over each group of prompts
        with the same template. This tells us what values to mask with.
    '''
    # Get the mask for this layer, and add d_head=1 dimension so it broadcasts correctly
    mask_for_this_layer = heads_and_posns_to_keep[hook.layer()].unsqueeze(-1).to(z.device)

    # Set z values to the mean 
    z = t.where(mask_for_this_layer, z, means[hook.layer()])

    return z


def compute_means_by_template(
    means_dataset: IOIDataset, 
    model: HookedTransformer
) -> Float[Tensor, "layer batch seq head_idx d_head"]:
    '''
    Returns the mean of each head's output over the means dataset. This mean is
    computed separately for each group of prompts with the same template (these
    are given by means_dataset.groups).
    '''
    # Cache the outputs of every head
    _, means_cache = model.run_with_cache(
        means_dataset.toks.long(),
        return_type=None,
        names_filter=lambda name: name.endswith("z"),
    )
    # Create tensor to store means
    n_layers, n_heads, d_head = model.cfg.n_layers, model.cfg.n_heads, model.cfg.d_head
    batch, seq_len = len(means_dataset), means_dataset.max_len
    means = t.zeros(size=(n_layers, batch, seq_len, n_heads, d_head), device=model.cfg.device)

    # Get set of different templates for this data
    for layer in range(model.cfg.n_layers):
        z_for_this_layer: Float[Tensor, "batch seq head d_head"] = means_cache[utils.get_act_name("z", layer)]
        for template_group in means_dataset.groups:
            z_for_this_template = z_for_this_layer[template_group]
            z_means_for_this_template = einops.reduce(z_for_this_template, "batch seq head d_head -> seq head d_head", "mean")
            means[layer, template_group] = z_means_for_this_template

    return means


def add_mean_ablation_hook(
    model: HookedTransformer, 
    means_dataset: IOIDataset, 
    circuit: Dict[str, List[Tuple[int, int]]] = CIRCUIT,
    seq_pos_to_keep: Dict[str, str] = SEQ_POS_TO_KEEP,
    is_permanent: bool = True,
) -> HookedTransformer:
    '''
    Adds a permanent hook to the model, which ablates according to the circuit and 
    seq_pos_to_keep dictionaries.

    In other words, when the model is run on ioi_dataset, every head's output will 
    be replaced with the mean over means_dataset for sequences with the same template,
    except for a subset of heads and sequence positions as specified by the circuit
    and seq_pos_to_keep dicts.
    '''
    
    model.reset_hooks(including_permanent=True)

    # Compute the mean of each head's output on the ABC dataset, grouped by template
    means = compute_means_by_template(means_dataset, model)
    
    # Convert this into a boolean map
    heads_and_posns_to_keep = get_heads_and_posns_to_keep(means_dataset, model, circuit, seq_pos_to_keep)

    # Get a hook function which will patch in the mean z values for each head, at 
    # all positions which aren't important for the circuit
    hook_fn = partial(
        hook_fn_mask_z, 
        heads_and_posns_to_keep=heads_and_posns_to_keep, 
        means=means
    )

    # Apply hook
    model.add_hook(lambda name: name.endswith("z"), hook_fn, is_permanent=is_permanent)

    return model
```
</details>


### Exercise - calculate minimality scores

```c
Difficulty: 🟠🟠🟠🟠🟠
Importance: 🟠🟠⚪⚪⚪

This exercise is expected to take a long time; at least an hour. It is probably the second most challenging exercise in this notebook.
```


We'll conclude this section by replicating figure 7 of the paper, which shows the minimality scores for the model.

Again, this exercise is very challenging and is designed to be done with minimal guidance. You will need to read the relevant sections of the paper which explain this plot: section 4 (experimental validation), from the start up to the end of section 4.2. Note that you won't need to perform the sampling algorithm described on page 10, because we're giving you the set $K$ for each component, in the form of the dictionary below (this is based on the information given in figure 20 of the paper, the "minimality sets" table).


```python

if MAIN:
    K_FOR_EACH_COMPONENT = {
        (9, 9): set(),
        (10, 0): {(9, 9)},
        (9, 6): {(9, 9), (10, 0)},
        (10, 7): {(11, 10)},
        (11, 10): {(10, 7)},
        (8, 10): {(7, 9), (8, 6), (7, 3)},
        (7, 9): {(8, 10), (8, 6), (7, 3)},
        (8, 6): {(7, 9), (8, 10), (7, 3)},
        (7, 3): {(7, 9), (8, 10), (8, 6)},
        (5, 5): {(5, 9), (6, 9), (5, 8)},
        (5, 9): {(11, 10), (10, 7)},
        (6, 9): {(5, 9), (5, 5), (5, 8)},
        (5, 8): {(11, 10), (10, 7)},
        (0, 1): {(0, 10), (3, 0)},
        (0, 10): {(0, 1), (3, 0)},
        (3, 0): {(0, 1), (0, 10)},
        (4, 11): {(2, 2)},
        (2, 2): {(4, 11)},
        (11, 2): {(9, 9), (10, 0), (9, 6)},
        (10, 6): {(9, 9), (10, 0), (9, 6), (11, 2)},
        (10, 10): {(9, 9), (10, 0), (9, 6), (11, 2), (10, 6)},
        (10, 2): {(9, 9), (10, 0), (9, 6), (11, 2), (10, 6), (10, 10)},
        (9, 7): {(9, 9), (10, 0), (9, 6), (11, 2), (10, 6), (10, 10), (10, 2)},
        (10, 1): {(9, 9), (10, 0), (9, 6), (11, 2), (10, 6), (10, 10), (10, 2), (9, 7)},
        (11, 9): {(9, 9), (10, 0), (9, 6), (9, 0)},
        (9, 0): {(9, 9), (10, 0), (9, 6), (11, 9)},
    }

```

Also, given a dictionary `minimality_scores` (which maps heads to their scores), the following code will produce a plot that looks like the one from the paper:


```python
def plot_minimal_set_results(minimality_scores: Dict[Tuple[int, int], float]):
    '''
    Plots the minimality results, in a way resembling figure 7 in the paper.

    minimality_scores:
        Dict with elements like (9, 9): minimality score for head 9.9 (as described
        in section 4.2 of the paper)
    '''
    
    CIRCUIT_reversed = {head: k for k, v in CIRCUIT.items() for head in v}
    colors = [CIRCUIT_reversed[head].capitalize() + " head" for head in minimality_scores.keys()]
    color_sequence = [px.colors.qualitative.Dark2[i] for i in [0, 1, 2, 5, 3, 6]] + ["#BAEA84"]

    bar(
        list(minimality_scores.values()),
        x=list(map(str, minimality_scores.keys())),
        labels={"x": "Attention head", "y": "Change in logit diff", "color": "Head type"},
        color=colors,
        template="ggplot2",
        color_discrete_sequence=color_sequence,
        bargap=0.02,
        yaxis_tickformat=".0%",
        legend_title_text="",
        title="Plot of minimality scores (as percentages of full model logit diff)",
        width=800,
        hovermode="x unified"
    )

```

```python
# FLAT SOLUTION NOINDENT
# YOUR CODE HERE - define the `minimality_scores` dictionary, to be used in the plot function given above
def get_score(
    model: HookedTransformer, 
    ioi_dataset: IOIDataset, 
    abc_dataset: IOIDataset,
    K: Set[Tuple[int, int]],
    C: Dict[str, List[Tuple[int, int]]],
) -> float:
    '''
    Returns the value F(C \ K), where F is the logit diff, C is the
    core circuit, and K is the set of circuit components to remove.
    '''
    C_excl_K = {k: [head for head in v if head not in K] for k, v in C.items()}
    model = add_mean_ablation_hook(model, abc_dataset, C_excl_K, SEQ_POS_TO_KEEP)
    logits = model(ioi_dataset.toks)
    score = logits_to_ave_logit_diff_2(logits, ioi_dataset).item()

    return score


def get_minimality_score(
    model: HookedTransformer,
    ioi_dataset: IOIDataset,
    abc_dataset: IOIDataset,
    v: Tuple[int, int],
    K: Set[Tuple[int, int]],
    C: Dict[str, List[Tuple[int, int]]] = CIRCUIT,
) -> float:
    '''
    Returns the value | F(C \ K_union_v) - F(C | K) |, where F is 
    the logit diff, C is the core circuit, K is the set of circuit
    components to remove, and v is a head (not in K).
    '''
    assert v not in K
    K_union_v = K | {v}
    C_excl_K_score = get_score(model, ioi_dataset, abc_dataset, K, C)
    C_excl_Kv_score = get_score(model, ioi_dataset, abc_dataset, K_union_v, C)

    return abs(C_excl_K_score - C_excl_Kv_score)


def get_all_minimality_scores(
    model: HookedTransformer,
    ioi_dataset: IOIDataset = ioi_dataset,
    abc_dataset: IOIDataset = abc_dataset,
    k_for_each_component: Dict = K_FOR_EACH_COMPONENT
) -> Dict[Tuple[int, int], float]:
    '''
    Returns dict of minimality scores for every head in the model (as 
    a fraction of F(M), the logit diff of the full model).

    Warning - this resets all hooks at the end (including permanent).
    '''
    # Get full circuit score F(M), to divide minimality scores by
    model.reset_hooks(including_permanent=True)
    logits = model(ioi_dataset.toks)
    full_circuit_score = logits_to_ave_logit_diff_2(logits, ioi_dataset).item()

    # Get all minimality scores, using the `get_minimality_score` function
    minimality_scores = {}
    for v, K in tqdm(k_for_each_component.items()):
        score = get_minimality_score(model, ioi_dataset, abc_dataset, v, K)
        minimality_scores[v] = score / full_circuit_score

    model.reset_hooks(including_permanent=True)

    return minimality_scores



if MAIN:
    minimality_scores = get_all_minimality_scores(model)
    # FLAT SOLUTION END

```

```python

if MAIN:
    plot_minimal_set_results(minimality_scores)

```

<details>
<summary>Hint (docstrings of some functions which will be useful for your main function)</summary>

```python
def get_score(
    model: HookedTransformer, 
    ioi_dataset: IOIDataset, 
    abc_dataset: IOIDataset,
    K: Set[Tuple[int, int]],
    C: Dict[str, List[Tuple[int, int]]],
) -> float:
    '''
    Returns the value F(C \ K), where F is the logit diff, C is the
    core circuit, and K is the set of circuit components to remove.
    '''
    pass


def get_minimality_score(
    model: HookedTransformer,
    ioi_dataset: IOIDataset,
    abc_dataset: IOIDataset,
    v: Tuple[int, int],
    K: Set[Tuple[int, int]],
    C: Dict[str, List[Tuple[int, int]]] = CIRCUIT,
) -> float:
    '''
    Returns the value | F(C \ K_union_v) - F(C | K) |, where F is 
    the logit diff, C is the core circuit, K is the set of circuit
    components to remove, and v is a head (not in K).
    '''
    pass


def get_all_minimality_scores(
    model: HookedTransformer,
    ioi_dataset: IOIDataset = ioi_dataset,
    abc_dataset: IOIDataset = abc_dataset,
    k_for_each_component: Dict = K_FOR_EACH_COMPONENT
) -> Dict[Tuple[int, int], float]:
    '''
    Returns dict of minimality scores for every head in the model (as 
    a fraction of F(M), the logit diff of the full model).

    Warning - this resets all hooks at the end (including permanent).
    '''
    pass


minimality_scores = get_all_minimality_scores(model)

plot_minimal_set_results(minimality_scores)
```

The output of the third function can be plotted using the plotting function given above.

</details>


<details>
<summary>Solution</summary>


</details>


Note - your results won't be exactly the same as the paper's, because of random error (e.g. the order of importanc of heads within each category might not be the same, especially heads with a small effect on the model like the backup name mover heads). But they should be reasonably similar in their important features.




""", unsafe_allow_html=True)


def section_6():

    st.sidebar.markdown(r"""

## Table of Contents

<ul class="contents">
    <li class='margtop'><a class='contents-el' href='#early-induction-heads'>Early induction heads</a></li>
    <li><ul class="contents">
        <li><a class='contents-el' href='#exercise-validate-prev-token-heads-via-patching'><b>Exercise</b> - validate prev token heads via patching</a></li>
    </ul></li>
    <li class='margtop'><a class='contents-el' href='#backup-name-mover-heads'>Backup name mover heads</a></li>
    <li class='margtop'><a class='contents-el' href='#positional-vs-token-information-being-moved'>Positional vs token information being moved</a></li>
    <li><ul class="contents">
        <li><a class='contents-el' href='#exercise-decompose-s-inhibition-heads'><b>Exercise</b> - decompose S-Inhibition heads</a></li>
    </ul></li>
    <li class='margtop'><a class='contents-el' href='#future-directions'>Future directions</a></li>
    <li class='margtop'><a class='contents-el' href='#further-reading'>Further Reading</a></li>
</ul></li>""", unsafe_allow_html=True)

    st.markdown(r"""

# 5️⃣ Bonus / exploring anomalies


> ##### Learning objectives
> 
> * Explore other parts of the model (e.g. negative name mover heads, and induction heads)
> * Understand the subtleties present in model circuits, and the fact that there are often more parts to a circuit than seem obvious after initial investigation
> * Understand the importance of the three quantitative criteria used by the paper: **faithfulness**, **completeness** and **minimality**


Here, you'll explore some weirder parts of the circuit which we haven't looked at in detail yet. Specifically, there are three parts to explore:

* Early induction heads
* Backup name mover heads
* Positional vs token information being moved

These three sections are all optional, and you can do as many of them as you want (in whichever order you prefer). There will also be some further directions of investigation at the end of this section, which have been suggested either by the authors or by Neel.


## Early induction heads


As we've discussed, a really weird observation is that some of the early heads detecting duplicated tokens are induction heads, not just direct duplicate token heads. This is very weird! What's up with that? 


First off, let's just recap what induction heads are. An induction head is an important type of attention head that can detect and continue repeated sequences. It is the second head in a two head induction circuit, which looks for previous copies of the current token and attends to the token *after* it, and then copies that to the current position and predicts that it will come next. They're enough of a big deal that [Anthropic wrote a whole paper on them](https://transformer-circuits.pub/2022/in-context-learning-and-induction-heads/index.html).

The diagram below shows a diagram for how they work to predict that the token `"urs"` follows `" D"`, the second time the word `"Dursley"` appears (note that we assume the model has not been trained on Harry Potter, so this is an example of in-context learning).

<img src="https://raw.githubusercontent.com/callummcdougall/computational-thread-art/master/example_images/misc/ih-simple.png" width="650">


Why is it surprising that induction heads up here? It's surprising because it feels like overkill. The model doesn't care about *what* token comes after the first copy of the subject, just that it's duplicated. And it already has simpler duplicate token heads. My best guess is that it just already had induction heads around and that, in addition to their main function, they *also* only activate on duplicated tokens. So it was useful to repurpose this existing machinery. 

This suggests that as we look for circuits in larger models life may get more and more complicated, as components in simpler circuits get repurposed and built upon. 


First, in the cell below, you should visualise the attention patterns of the induction heads (`5.5` and `6.9`) on sequences containg repeated tokens, and verify that they are attending to the token *after* the previous instance of that same token. You might want to repeat code you wrote in the "Validation of duplicate token heads" section.


```python

if MAIN:
    model.reset_hooks(including_permanent=True)
    
    attn_heads = [(5, 5), (6, 9)]
    
    # Get repeating sequences (note we could also take mean over larger batch)
    batch = 1
    seq_len = 15
    rep_tokens = generate_repeated_tokens(model, seq_len, batch)
    
    # Run cache (we only need attention patterns for layers 5 and 6)
    _, cache = model.run_with_cache(
        rep_tokens,
        return_type = None,
        names_filter = lambda name: name.endswith("pattern") and any(f".{layer}." in name for layer, head in attn_heads)
    )
    
    # Display results
    attn = t.stack([
        cache["pattern", layer][0, head]
        for (layer, head) in attn_heads
    ])
    cv.attention.attention_patterns(
        tokens = model.to_str_tokens(rep_tokens[0]),
        attention = attn,
        attention_head_names = [f"{layer}.{head}" for (layer, head) in attn_heads]
    )

```

One implication of this is that it's useful to categories heads according to whether they occur in simpler circuits, so that as we look for more complex circuits we can easily look for them. This is Hooked to do here! An interesting fact about induction heads is that they work on a sequence of repeated random tokens - notable for being wildly off distribution from the natural language GPT-2 was trained on. Being able to predict a model's behaviour off distribution is a good mark of success for mechanistic interpretability! This is a good sanity check for whether a head is an induction head or not. 

We can characterise an induction head by just giving a sequence of random tokens repeated once, and measuring the average attention paid from the second copy of a token to the token after the first copy. At the same time, we can also measure the average attention paid from the second copy of a token to the first copy of the token, which is the attention that the induction head would pay if it were a duplicate token head, and the average attention paid to the previous token to find previous token heads.

Note that this is a superficial study of whether something is an induction head - we totally ignore the question of whether it actually does boost the correct token or whether it composes with a single previous head and how. In particular, we sometimes get anti-induction heads which suppress the induction-y token (no clue why!), and this technique will find those too.


### Exercise - validate prev token heads via patching

```c
Difficulty: 🟠🟠⚪⚪⚪
Importance: 🟠🟠⚪⚪⚪

This just involves performing a specific kind of patching, with functions you've already written.
```

The paper mentions that heads `2.2` and `4.11` are previous token heads. Hopefully you already validated this in the previous section by plotting the previous token scores (in your replication of Figure 18). But this time, you'll perform a particular kind of path patching to prove that these heads are functioning as previous token heads, in the way implied by our circuit diagram.

<details>
<summary>Question - what kind of path patching should you perform?</summary>

To show these heads are acting as prev token heads in an induction circuit, we want to perform key-patching (i.e. patch the path from the output of the prev token heads to the key inputs of the induction heads).

We expect this to worsen performance, because it interrupts the duplicate token signal provided by the induction heads.
</details>


```python

if MAIN:
    model.reset_hooks(including_permanent=True)
    
    # YOUR CODE HERE - create `induction_head_key_path_patching_results` 

```

```python

if MAIN:
    imshow(
        100 * induction_head_key_path_patching_results,
        title="Direct effect on Induction Heads' keys", 
        labels={"x": "Head", "y": "Layer", "color": "Logit diff.<br>variation"},
        coloraxis=dict(colorbar_ticksuffix = "%"),
        width=600,
    )

```

<details>
<summary>Solution</summary>

```python
model.reset_hooks(including_permanent=True)

induction_head_key_path_patching_results = get_path_patch_head_to_heads(
    receiver_heads = [(5, 5), (6, 9)],
    receiver_input = "k",
    model = model,
    patching_metric = ioi_metric_2
)
```
</details>


You might notice that there are two other heads in the induction heads box in the paper's diagram, both in brackets (heads `5.8` and `5.9`). Can you try and figure out what these heads are doing, and why they're in brackets?


<details>
<summary>Hint</summary>

Recall the path patching section, where you applied patching from attention heads' outputs to the value inputs to the S-inhibition heads (hopefully replicating figure 4b from the paper). Try patching the **keys** of the S-inhibition heads instead. Do heads `5.8` and `5.9` stand out here?
</details>

<details>
<summary>Answer</summary>

After making the plot suggested in the hint, you should find that patching from `5.8` and `5.9` each have around a 5% negative impact on the logit difference if you patch from them to the S-inhibition heads. We'd like to conclude that these are induction heads, and they're acting to increase the attention paid by `end` to `S2`. Unfortunately, they don't seem to be induction heads according to the results of figure 18 in the paper (which we replicated in the section "validation of early heads").

It turns out that they're acting as induction heads on this distribution, but not in general. A simple way we can support this hypothesis is to look at attention patterns (we find that `S2` pays attention to `S1+1` in both head `5.8` and `5.9`).
</details>

<details>
<summary>Aside - a lesson in nonlinearity</summary>

In the dropdown above, I claimed that `5.8` and `5.9` were doing induction on this distribution. A more rigorous way to test this would be to path patch to the keys of these heads, and see if either of the previous token heads have a large effect. If they do, this is very strong evidence for induction. However, it turns out that neither of the prev token heads affect the model's IOI performance via their path through the fuzzy induction heads. Does this invalidate our hypothesis?

In fact, no, because of nonlinearity. The two prev token heads `2.2` and `4.11` will be adding onto the **logits** used to calculate the attention probability from `S2` to `S1+1`, rather than adding onto the probabilities directly. SO it might be the case that one head on its own doesn't increase the attention probability very much, both both heads acting together significantly increase it. (Motivating example: suppose we only had 2 possible source tokens, without either head acting the logits are `[0.0, -8.0]`, and the action of each head is to add `4.0` to the second logit. If one head acts then the probability on the second token goes from basically zero to `0.018` (which will have a very small impact on the attention head's output), but if both heads are acting then the logits are equal and the probability is `0.5` (which obviously has a much larger effect)).

This is in fact what I found here - after modifying the path patching function to allow more than one sender head, I found that patching from both `2.2` and `4.11` to `5.8` and `5.9` had a larger effect on the model's IOI performance than patching from either head alone (about a 1% drop in performance for both vs almost 0% for either individually). The same effect can be found when we patch from these heads to all four induction heads, although it's even more pronounced (a 3% and 15% drop respectively for the heads individually, vs 31% for both).
</details>


## Backup name mover heads


Another fascinating anomaly is that of the **backup name mover heads**. A standard technique to apply when interpreting model internals is ablations, or knock-out. If we run the model but intervene to set a specific head to zero, what happens? If the model is robust to this intervention, then naively we can be confident that the head is not doing anything important, and conversely if the model is much worse at the task this suggests that head was important. There are several conceptual flaws with this approach, making the evidence only suggestive, e.g. that the average output of the head may be far from zero and so the knockout may send it far from expected activations, breaking internals on *any* task. But it's still an Hooked technique to apply to give some data.

But a wild finding in the paper is that models have **built in redundancy**. If we knock out one of the name movers, then there are some backup name movers in later layers that *change their behaviour* and do (some of) the job of the original name mover head. This means that naive knock-out will significantly underestimate the importance of the name movers.



Let's test this! Let's ablate the most important name mover (which is `9.9`, as the code below verifies for us) on just the `end` token, and compare performance.


```python

if MAIN:
    model.reset_hooks(including_permanent=True)
    
    ioi_logits, ioi_cache = model.run_with_cache(ioi_dataset.toks)
    original_average_logit_diff = logits_to_ave_logit_diff_2(ioi_logits)

```

```python

if MAIN:
    s_unembeddings = model.W_U.T[ioi_dataset.s_tokenIDs]
    io_unembeddings = model.W_U.T[ioi_dataset.io_tokenIDs]
    logit_diff_directions: Float[Tensor, "batch d_model"] =  io_unembeddings - s_unembeddings
    
    per_head_residual, labels = ioi_cache.stack_head_results(layer=-1, return_labels=True)
    per_head_residual = einops.rearrange(
        per_head_residual[:, t.arange(len(ioi_dataset)).to(device), ioi_dataset.word_idx["end"].to(device)], 
        "(layer head) batch d_model -> layer head batch d_model", 
        layer=model.cfg.n_layers
    )
    
    per_head_logit_diffs = residual_stack_to_logit_diff(per_head_residual, ioi_cache, logit_diff_directions)
    
    top_layer, top_head = topk_of_Nd_tensor(per_head_logit_diffs, k=1)[0]
    print(f"Top Name Mover to ablate: {top_layer}.{top_head}")

```

```python
# Getting means we can use to ablate

if MAIN:
    abc_means = ioi_circuit_extraction.compute_means_by_template(abc_dataset, model)[top_layer]
    
    # Define hook function and add to model
def ablate_top_head_hook(z: Float[Tensor, "batch pos head_index d_head"], hook):
    '''
    Ablates hook by patching in results
    '''
    z[range(len(ioi_dataset)), ioi_dataset.word_idx["end"], top_head] = abc_means[range(len(ioi_dataset)), ioi_dataset.word_idx["end"], top_head]
    return z


if MAIN:
    model.add_hook(utils.get_act_name("z", top_layer), ablate_top_head_hook)
    
    # Runs the model, temporarily adds caching hooks and then removes *all* hooks after running, including the ablation hook.
    ablated_logits, ablated_cache = model.run_with_cache(ioi_dataset.toks)
    rprint("\n".join([
        f"                            Original logit diff: {original_average_logit_diff:.4f}",
        f"Direct Logit Attribution of top name mover head: {per_head_logit_diffs[top_layer, top_head]:.4f}",
        f"   Naive prediction of post ablation logit diff: {original_average_logit_diff - per_head_logit_diffs[top_layer, top_head]:.4f}",
        f"      Logit diff after ablating L{top_layer}H{top_head}: {logits_to_ave_logit_diff_2(ablated_logits):.4f}",
    ]))

```

```python

if MAIN:
    make_table(
        cols = [
            "Original logit diff", "Direct Logit Attribution of top name mover head", "Naive prediction of post ablation logit diff", f"Logit diff after ablating L{top_layer}H{top_head}",
            original_average_logit_diff, per_head_logit_diffs[top_layer, top_head]
        ]
    )

```

What's going on here? We calculate the logit diff for our full model, and how much of that is coming directly from head `9.9`. Given this, we might guess that when we ablate this head, the logit diff will drop down to `3.07768 - 1.7230 = 1.3538`. Instead, we find that the logit diff is `2.8116`, in other words it drops much less than we expected.

Why is this happening? As before, we can look at the direct logit attribution of each head to get a sense of what's going on.


```python

if MAIN:
    per_head_ablated_residual, labels = ablated_cache.stack_head_results(layer=-1, return_labels=True)
    per_head_ablated_residual = einops.rearrange(
        per_head_ablated_residual[:, t.arange(len(ioi_dataset)).to(device), ioi_dataset.word_idx["end"].to(device)], 
        "(layer head) batch d_model -> layer head batch d_model", 
        layer=model.cfg.n_layers
    )
    per_head_ablated_logit_diffs = residual_stack_to_logit_diff(per_head_ablated_residual, ablated_cache, logit_diff_directions)
    per_head_ablated_logit_diffs = per_head_ablated_logit_diffs.reshape(model.cfg.n_layers, model.cfg.n_heads)
    
    imshow(
        t.stack([
            per_head_logit_diffs, 
            per_head_ablated_logit_diffs, 
            per_head_ablated_logit_diffs - per_head_logit_diffs
        ]), 
        title="Direct logit contribution by head, pre / post ablation",
        labels={"x":"Head", "y":"Layer"},
        facet_col=0,
        facet_labels=["No ablation", "9.9 is ablated", "Change in head contribution post-ablation"],
    )
    
    scatter(
        y=per_head_logit_diffs.flatten(), 
        x=per_head_ablated_logit_diffs.flatten(), 
        hover_name=labels, 
        range_x=(-1, 1), 
        range_y=(-2, 2), 
        labels={"x": "Ablated", "y": "Original"},
        title="Original vs Post-Ablation Direct Logit Attribution of Heads",
        width=600,
        add_line="y=x"
    )

```

The first plots show us that, after we ablate head `9.9`, while its direct contribution to the logit diff falls (obviously), a lot of contributions from other heads (particularly in layer 10) actually increase. The second plot shows this in a different way (the distinctive heads in the right hand heatmap are the same as the heads lying well below the y=x line in the scatter plot).

One natural hypothesis is that this is because the final LayerNorm scaling has changed, which can scale up or down the final residual stream. This is slightly true, and we can see that the typical head is a bit off from the x=y line. But the average LN scaling ratio is 1.04, and this should uniformly change *all* heads by the same factor, so this can't be sufficient.


```python

if MAIN:
    ln_scaling_no_ablation = ioi_cache["ln_final.hook_scale"][t.arange(len(ioi_dataset)), ioi_dataset.word_idx["end"]].squeeze()
    ln_scaling_ablated = ablated_cache["ln_final.hook_scale"][t.arange(len(ioi_dataset)), ioi_dataset.word_idx["end"]].squeeze()

```

```python

if MAIN:
    scatter(
        y=ln_scaling_ablated,
        x=ln_scaling_no_ablation,
        labels={"x": "No ablation", "y": "Ablation"},
        title=f"Final LN scaling factors compared (ablation vs no ablation)<br>Average ratio = {(ln_scaling_no_ablation / ln_scaling_ablated).mean():.4f}",
        width=700,
        add_line="y=x"
    )

```

**Exercise to the reader:** Can you finish off this analysis? What's going on here? Why are the backup name movers changing their behaviour? Why is one negative name mover becoming significantly less important?


## Positional vs token information being moved

In section A of the appendix (titled **Disentangling token and positional signal in the output of S-Inhibition Heads**), the authors attempt to figure out whether the S-Inhibition heads are using token or positional information to supress the attention paid to `S1`. This is illustrated in my IOI diagram, by purple vs pink boxes.

The way the authors find out which one is which is ingenious. They construct datasets from the original IOI dataset, with some of the signals erased or flipped. For instance, if they want to examine the effect of inverting the positional information but preserving the token information written by the S-inhibition heads, they can replace sentences like:

```
When Mary and John went to the store, John gave a drink to Mary
```

with:

```
When John and Mary went to the store, John gave a drink to Mary
```

Let's be exactly clear on why this works. The information written to the `end` token position by the S-inhibition heads will be some combination of "don't pay attention to the duplicated token" and "don't pay attention to the token that's in the same position as the duplicated token". If we run our model on the first sentence above but then patch in the second sentence, then:

* The **"don't pay attention to the duplicated token"** signal will be unchanged (because this signal still refers to John)
* The **"don't pay attention to the token that's in the same position as the duplicated token"** signal will flip (because this information points to the position of `Mary` in the second sentence, hence to the position of `John` in the first sentence).


That was just one example (flipping positional information, keeping token information the same), but we can do any of six different types of flip:


| Token signal | Positional signal | Sentence                                                          | ABB -> ? |
| ------------ | ----------------- | ----------------------------------------------------------------- | -------- |
| Same         | Same              | `When Mary and John went to the store, John gave a drink to Mary` | ABB      |
| Random       | Same              | `When Emma and Paul went to the store, Paul gave ...`             | CDD      |
| Inverted     | Same              | `When John and Mary went to the store, Mary gave ...`             | BAA      |
| Same         | Inverted          | `When John and Mary went to the store, John gave ...`             | BAB      |
| Random       | Inverted          | `When Paul and Emma went to the store, Emma gave ...`             | DCD      |
| Inverted     | Inverted          | `When Mary and John went to the store, Mary gave ...`             | ABA      |


We use the `gen_flipped_prompts` method to generate each of these datasets:


```python

if MAIN:
    datasets: List[Tuple[Tuple, str, IOIDataset]] = [
        ((0, 0), "original", ioi_dataset),
        ((1, 0), "random token", ioi_dataset.gen_flipped_prompts("ABB->CDD, BAB->DCD")),
        ((2, 0), "inverted token", ioi_dataset.gen_flipped_prompts("ABB->BAA, BAB->ABA")),
        ((0, 1), "inverted position", ioi_dataset.gen_flipped_prompts("ABB->BAB, BAB->ABB")),
        ((1, 1), "inverted position, random token", ioi_dataset.gen_flipped_prompts("ABB->DCD, BAB->CDD")),
        ((2, 1), "inverted position, inverted token", ioi_dataset.gen_flipped_prompts("ABB->ABA, BAB->BAA")),
    ]

```

*Note - the purpose of the type annotation for `datasets` is so that, when we iterate through datasets, the type checker can identify the third item in each iterate as an `IOIDataset`, and autocomplete methods for us.*


```python

if MAIN:
    results = t.zeros(3, 2).to(device)
    
    s2_inhibition_heads = CIRCUIT["s2 inhibition"]
    layers = set(layer for layer, head in s2_inhibition_heads)
    
    names_filter=lambda name: name in [utils.get_act_name("z", layer) for layer in layers]
    
def patching_hook_fn(z: Float[Tensor, "batch seq head d_head"], hook: HookPoint, cache: ActivationCache):
    heads_to_patch = [head for layer, head in s2_inhibition_heads if layer == hook.layer()]
    z[:, :, heads_to_patch] = cache[hook.name][:, :, heads_to_patch]
    return z


if MAIN:
    for ((row, col), desc, dataset) in datasets:
    
        # Get cache of values from the modified dataset
        _, cache_for_patching = model.run_with_cache(
            dataset.toks,
            names_filter=names_filter,
            return_type=None
        )
    
        # Run model on IOI dataset, but patch S-inhibition heads with signals from modified dataset
        patched_logits = model.run_with_hooks(
            ioi_dataset.toks,
            fwd_hooks=[(names_filter, partial(patching_hook_fn, cache=cache_for_patching))]
        )
    
        # Get logit diff for patched results
        # Note, we still use IOI dataset for our "correct answers" reference point
        results[row, col] = logits_to_ave_logit_diff_2(patched_logits, ioi_dataset)

```

```python

if MAIN:
    imshow(
        results, 
        labels={"x": "Positional signal", "y": "Token signal"}, 
        x=["Original", "Inverted"], 
        y=["Original", "Random", "Inverted"], 
        title="Logit diff after changing all S2 inhibition heads' output signals via patching",
        text_auto=".2f"
    )

```

What are your interpretations of this plot?

<details>
<summary>Some thoughts</summary>

A few sanity checks, which are what we'd expect from this plot (and hence validate our code as probably being correct):

* When token and positional signals are inverted, performance is close to negative of the original performance.
* Inverting the positional signal makes performance worse.
* Randomizing the token signal makes performance worse. 
* Inverting the token signal makes performance worse. This effect is larger than randomizing (because we're pointing away from a correct answer, rather than just in a random direction).

There are two main interesting findings from this plot (which we might have guessed at beforehand, but couldn't have been certain about):
* The row and column differences are close to constant (column diff is approx 4.5, row diff is approx 0.75). In other words, the logit diff can be well approximated by a linear combination of the positional and token signal correlations (where correlation is 1 if the signal points towards the correct value, -1 if it points away, and 0 if it points in a random direction).
* The coefficients on the positional signal correlation is **much** bigger than the coefficient on the token signal correlation. The former is about 4.5, the latter is about 1.5. This tells us that positional information is a lot more important than token information.
    * One possible intuition here is that name information (i.e. representing the identity of the token `" John"`) takes up many dimensions, so is probably harder for the model. Relative positional information on the other hand will mostly have fewer dimensions. Since the model only needs to move enough information to single out a single positional index from about 15-20, rather than single out a name in the entire set of names. This is jus a guess though, and I'd love to hear other interpretations.

</details>


Let's dig a little deeper. Rather than just looking at the S-inhibition heads collectively, we can look at each of them individually.


### Exercise - decompose S-Inhibition heads

```c
Difficulty: 🟠🟠⚪⚪⚪
Importance: 🟠🟠🟠⚪⚪

You should spend up to 10-15 minutes on this exercise.

This involves a lot of duplicating code from above.
```

Make the same plot as above, but after intervening on each of the S-inhibition heads individually. 

You can do this by creating a `results` tensor of shape `(M, 3, 2)` where `M` is the number of S-inhibition heads, and each slice contains the results of intervening on that particular head, then using the `facet` arguments of the `imshow` function:

(You might prefer to plot the results in the form of "change in logit diff from clean value, as a fraction of clean value", to make the results look clearer.)


```python

if MAIN:
    results = t.zeros(len(CIRCUIT["s2 inhibition"]), 3, 2).to(device)
    # Your code here - fill in results!
    
def patching_hook_fn(
    z: Float[Tensor, "batch seq head d_head"], 
    hook: HookPoint, 
    cache: ActivationCache, 
    head: int
):
    z[:, :, head] = cache[hook.name][:, :, head]
    return z


if MAIN:
    for i, (layer, head) in enumerate(CIRCUIT["s2 inhibition"]):
    
        model.reset_hooks(including_permanent=True)
    
        hook_name = utils.get_act_name("z", layer)
    
        for ((row, col), desc, dataset) in datasets:
    
            # Get cache of values from the modified dataset
            _, cache_for_patching = model.run_with_cache(
                dataset.toks,
                names_filter=lambda name: name == hook_name,
                return_type=None
            )
    
            # Run model on IOI dataset, but patch S-inhibition heads with signals from modified dataset
            patched_logits = model.run_with_hooks(
                ioi_dataset.toks,
                fwd_hooks=[(hook_name, partial(patching_hook_fn, cache=cache_for_patching, head=head))]
            )
    
            # Get logit diff for patched results
            # Note, we still use IOI dataset for our "correct answers" reference point
            results[i, row, col] = logits_to_ave_logit_diff_2(patched_logits, ioi_dataset)

```

```python

if MAIN:
    imshow(
        (results - results[0, 0, 0]) / results[0, 0, 0], 
        labels={"x": "Positional signal", "y": "Token signal"}, 
        x=["Original", "Inverted"], 
        y=["Original", "Random", "Inverted"], 
        title="Logit diff after patching individual S2 inhibition heads (as proportion of clean logit diff)",
        facet_col=0,
        facet_labels=[f"{layer}.{head}" for (layer, head) in CIRCUIT["s2 inhibition"]],
        facet_col_spacing = 0.08,
        text_auto=".2f",
    )

```

<details>
<summary>Solution</summary>

```python
def patching_hook_fn(z: Float[Tensor, "batch seq head d_head"], hook: HookPoint, cache: ActivationCache, head: int):
    z[:, :, head] = cache[hook.name][:, :, head]
    return z

for i, (layer, head) in enumerate(CIRCUIT["s2 inhibition"]):

    model.reset_hooks(including_permanent=True)

    hook_name = utils.get_act_name("z", layer)

    for ((row, col), desc, dataset) in datasets:

        # Get cache of values from the modified dataset
        _, cache_for_patching = model.run_with_cache(
            dataset.toks,
            names_filter=lambda name: name == hook_name,
            return_type=None
        )

        # Run model on IOI dataset, but patch S-inhibition heads with signals from modified dataset
        patched_logits = model.run_with_hooks(
            ioi_dataset.toks,
            fwd_hooks=[(hook_name, partial(patching_hook_fn, cache=cache_for_patching, head=head))]
        )

        # Get logit diff for patched results
        # Note, we still use IOI dataset for our "correct answers" reference point
        results[i, row, col] = logits_to_ave_logit_diff(patched_logits, ioi_dataset)
```

</details>


Noteworthy features of this plot:

* Every head cares more about positional signal than token signal
* Head `8.6` (the biggest S-inhibition head) cares MUCH more about positional signal, in fact it doesn't care at all about token signal
    * Suggests maybe `8.6` was the first head which learned to do this task, and subsequent heads basically just helped out by providing the remainder (which was token signal). Shows the heads specialise.
* The only heads that kinda care about token signal are `7.9` and `8.10` (but they still both care about positional signal almost twice as much)
* The approximation of logit diff as a sum of positional and token signal correlations still seems to hold for each head individually, although the coefficients for each head are different.


## Future directions

Here are some future directions, some suggested by Neel, others by the authors of the paper:


* 3 letter acronyms (or more!)
* Converting names to emails.
    * An extension task is e.g. constructing an email from a snippet like the following: Name: Neel Nanda; Email: last name dot first name k @ gmail
* Grammatical rules
    * Learning that words after full stops are capital letters
    * Verb conjugation
    * Choosing the right pronouns (e.g. he vs she vs it vs they)
    * Whether something is a proper noun or not
* Detecting sentiment (e.g. predicting whether something will be described as good vs bad)
* Interpreting memorisation. E.g., there are times when GPT-2 knows surprising facts like people’s contact information. How does that happen?
* Counting objects described in text. E.g.: I picked up an apple, a pear, and an orange. I was holding three fruits.
* Extensions from Alex Variengien
    * Understanding what's happening in the adversarial examples: most notably S-Inhibition Head attention pattern (hard). (S-Inhibition heads are mentioned in the IOI paper)
    * Understanding how are positional signal encoded (relative distance, something else?) bonus point if we have a story that include the positional embeddings and that explain how the difference between position is computed (if relative is the right framework) by Duplicate Token Heads / Induction Heads. (hard, but less context dependant)
    * What are the role of MLPs in IOI (quite broad and hard)
    * What is the role of Duplicate Token Heads outside IOI? Are they used in other Q-compositions with S-Inhibition Heads? Can we describe how their QK circuit implement "collision detection" at a parameter level? (Last question is low context dependant and quite tractable)
    * What is the role of Negative/ Backup/ regular Name Movers Heads outside IOI? Can we find examples on which Negative Name Movers contribute positively to the next-token prediction?
    * What are the differences between the 5 inductions heads present in GPT2-small? What are the heads they rely on / what are the later heads they compose with (low context dependence form IOI)
    * Understanding 4.11, (a really sharp previous token heads) at the parameter level. I think this can be quite tractable given that its attention pattern is almost perfectly off-diagonal
* What are the conditions for compensation mechanisms to occur? Is it due to drop-out? (Arthur Conmy is working on this - feel free to reach out to arthur@rdwrs.com )
* Extensions from Arthur Conmy
    * Understand IOI in GPT-Neo: it's a same size model but does IOI via composition of MLPs
    * Understand IOI in the Stanford mistral models - they all seem to do IOI in the same way, so maybe look at the development of the circuit through training?
* [Help out Redwood Research’s interpretability team by finding heuristics implemented by GPT-2 small](https://www.lesswrong.com/posts/LkBmAGJgZX2tbwGKg/help-out-redwood-research-s-interpretability-team-by-finding)
    * This LessWrong post from 6 months ago outlines some features of the IOI task that made it a good choice to study, and suggests other tasks that might meet these criteria / how you might go about finding such tasks.


## Further Reading

Here is a collection of links for further reading, which haven't already been mentioned:

* [Some Lessons Learned from Studying Indirect Object Identification in GPT-2 small](https://www.alignmentforum.org/posts/3ecs6duLmTfyra3Gp/some-lessons-learned-from-studying-indirect-object)
    * A blog post by the authors of this paper, which goes into more detail about the experiments and results.
* [Causal Scrubbing: a method for rigorously testing interpretability hypotheses [Redwood Research]](https://www.alignmentforum.org/posts/JvZhhzycHu2Yd57RN/causal-scrubbing-a-method-for-rigorously-testing)
    * Introduces the idea of causal scubbing, a proposed systematic method for evaluting the quality of mechanistic interpretations




""", unsafe_allow_html=True)


func_page_list = [
    (section_0, "🏠 Home"),     (section_1, "1️⃣ Model & Task Setup"),     (section_2, "2️⃣ Logit Attribution"),     (section_3, "3️⃣ Activation Patching"),     (section_4, "4️⃣ Path Patching"),     (section_5, "5️⃣ Paper Replication"),     (section_6, "5️⃣ Bonus / exploring anomalies"), 
]

func_list = [func for func, page in func_page_list]
page_list = [page for func, page in func_page_list]

page_dict = dict(zip(page_list, range(len(page_list))))

def page():
    with st.sidebar:
        radio = st.radio("Section", page_list)
        st.markdown("---")
    idx = page_dict[radio]
    func = func_list[idx]
    func()

page()
