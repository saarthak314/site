title: why you should learn ocaml
date: 2025-07-30
updated: 2026-08-26
description: a case for learning ocaml, functional programming, and a cleaner way to reason about software.
aliases:
  - /writeups/learn_ocaml/
-----

the ideas here apply to functional programming in general, but i'll focus on ocaml.

## empty the cup

> Nan-in (南隠), a Japanese master during the Meiji era (1868-1912), received a university professor who came to inquire about Zen. Nan-in served tea. He poured his visitor's cup full, then kept pouring. The professor watched the overflow until he could no longer restrain himself. "It is overfull. No more will go in!" "Like this cup," Nan-in said, "you are full of your own opinions and speculations. How can I show you Zen unless you first empty your cup?"

## why ocaml

how can learning ocaml make you a better programmer? you will:

- experience the freedom of _immutability_, fuck debugging
- improve at _abstraction_, fuck bloated code (luke smith giggles)
- learn a better _type system_, fuck failing tests
- get exposed to some _theory and implementation of programming languages_

ocaml will change the way you think about programming.

> _a language that doesn't affect the way you think about programming is not worth knowing._
>
> -- alan j. perlis, first recipient of the turing award

moreover, ocaml is beautiful. some normies might not agree to this statement but **aesthetics do matter**. ocaml is elegant, simple and graceful.

fyi, ocaml stands for _objective caml_. read [more](https://cs3110.github.io/textbook/chapters/intro/past.html) about its history.

![ritsuko holding orly](/images/ritsuko.webp)

ocaml is _awesome_ due to:

- immutable programming
- algebraic datatype and pattern matching
- first-class functions
- static type-checking
- auto type inference
- parametric polymorphism
- garbage collection
- modules

before moving on, you need to understand that **languages are tools**. each language is meant for a specific job:

- there is no universally perfect tool
- hence, there is no universally perfect language

## the functional model

a functional language:

- defines computations as _mathematical functions_
- avoids mutable _state_

**state**: the info maintained by a computation

back to basics, what is the difference between a functional programming language (ocaml, haskell, lisp, etc) and an imperative programming language (c++, java, python, etc)?

the key linguistic abstraction of _functional languages_ is a mathematical function. a function maps an input to an output and for the same input, it always produces the same output. which means that mathematical functions are _stateless_: they don't maintain any extra info or _state_ that persists between usages of the function.

functions are _first-class_: you can use them as input to other functions, and produce functions as output. expressing everything in terms of function enables a uniform and simple programming model that is easier to reason than the procedures and methods found in other langs.

now, _imperative languages_ involve _mutable_ state that changes throughout execution. commands specify how to compute by destructively changing that state. procedures/methods can have _side effects_ that update state in addition to producing a return value.

an example of destructive state change is:

```
x = x + 1
```

now this may seem fine to you, but this will trigger any mathematician.

## mutability is the trap

but why is _mutability_ bad?

the **fantasy** of mutability: it's easy to reason about because the computer does operations step by step.

the **reality** of mutability: machines are good at complicated state manipulation; humans are not. mutability breaks _referential transparency_: the ability to replace an expression with its value w/o affecting the result of a computation.

in math, $f(x) = y$, then you can substitute $y$ anywhere you see $f(x)$. in imperative languages, you cannot: $f$ might have side effects, so computing $f(x)$ at time $t$ might result in a different value than at time $t0$.

it makes it tempting to believe that there's a single state that the machine manipulates and that the computer only does one thing at a time. computer systems go to great lengths in attempting to provide this illusion. but this in fact is just an _illusion_. in reality, there are many states, spread across threads, cores, processors, and networked systems and it all works concurrently. mutability makes reasoning about distributed state and concurrent execution immensely difficult.

![immutability](/images/immutability.webp)

_immutability_, however, frees the programmer from these concerns. it provides powerful methods to build correct and concurrent programs.

in functional langs:

_expressions_ specify **what to compute**

- variables never change value (this may break the notion of calling them "variables"; identifier would be more accurate, but variable is the word everyone uses)
- functions never have side effects

## where ocaml shows up

ocaml and other functional langs are nowhere near as popular as python, c++, or java. ocaml's real strength lies in language manipulation: compilers, analyzers, verifiers, provers, etc. it evolved from the domain of theorem proving, after all.

but that doesn't mean that functional langs aren't used in the industry, there are many [industry](https://ocaml.org/learn/companies.html) using ocaml and haskell. some of the major ones are:

- facebook: created a language Reason also known as ReasonML i.e syntax extension and toolchain for ocaml. fun fact, it was created by jordan walke who also created react framework at facebook. reason uses many syntax elements from javascript, compiles to native code using ocaml's compiler toolchain, and can compile to javascript using the _rescript_ compiler.

while reason compiles down to native code via ocaml's toolchain, it specifically differs in the syntax, error messages and editor tooling which provides similar experience to javascript or typescript for devs

ex:

```
type schoolPerson = Teacher | Director | Student(string);
let greeting = person =>
  switch (person) {
  | Teacher => "Hey Professor!"
  | Director => "Hello Director."
  | Student("Richard") => "Still here Ricky?"
  | Student(anyOtherName) => "Hey, " ++ anyOtherName ++ "."
  };
```

reason is for front end dev which solves the problem of js lack of compile time typing.

- jane street: the largest commercial user of ocaml in the industry by a huge margin, for those who don't know jane street is a quantitative trading firm based in nyc. they are using ocaml for everything from research tools to trading systems to systems infra to accounting systems. 

they have over 500 hundred ocaml programmers and over 30 million lines of ocaml. nearly a million lines of their code are open source. moreover, they've created key parts of the open-source ocaml ecosystem, like dune (community de facto build system) [tech blog discussing dune](https://blog.janestreet.com/how-we-accidentally-built-a-better-build-system-for-ocaml-index/); core (alternative standard library); async (cooperative concurrency library) and most recently [OxCaml](https://blog.janestreet.com/introducing-oxcaml/) i.e fast-moving set of extensions to the ocaml language.

quoted from their blog:

> OxCaml is both **Jane Street’s production compiler**, as well as a **laboratory for experiments** focused towards making OCaml better for performance-oriented programming

head of technology at jane street (yaron minsky) published a [paper](https://www.cambridge.org/core/journals/journal-of-functional-programming/article/caml-trading-experiences-with-functional-programming-on-wall-street/02F18023B4C43BF6E53512AA7062A9A5) about using ocaml in the financial industry, i highly recommend you to read this paper.

- another project is multicore ocaml, covered in this [technical paper](https://kcsrk.info/papers/multicore-ocaml20.pdf). jane street has been instrumental here, funding research in multicore ocaml and the compiler for 10+ years through the ocaml labs initiative at the university of cambridge. the tools and compiler team also works directly with multicore ocaml developers. [another paper](https://dl.acm.org/doi/10.1145/3192366.3192421) dives deeper into how multicore works.

some other major corps that use ocaml are bloomberg, docker, cea-list, simcorp, etc. see [more](https://ocaml.org/industrial-users/businesses).

if this does sound interesting to you, then ask yourself what's stopping you from learning ocaml?
