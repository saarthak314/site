title: "winning #3 in amazon ml challenge"
date: 2026-10-08
description: "how to get #3 in amazon ml hackathon under 24 hrs w/ free compute"
-----

![final public leaderboard with our team in third place](/images/amazon-ml-third.webp "third place on the public leaderboard")

title is neither a joke nor me being cocky (debatable), but the competition is not that hard that you need to rent big boy GPUs or break into your university lab to access them. efficiency opens doors that bruteforcing can't even fathom of.

![our latest submission on the competition page](/images/amazon-ml-submission.webp "our latest submission, 10 mins prior to the deadline")

pretty sure if you are here then you dont need any introduction to the competition but to put out the context clearly so we can get to the same page.

## problem statement

> Link 24.2M business records: for each S1, find every S2/S3 copy of the same business. Train has US and India; test adds *France with no labels*. The metric is macro F0.5, where a wrong link costs 4× a miss.

so yeah, France was the main bottleneck for the benchmark. more on this later.

## solution pipeline

not exact, but design in a nutshell:

> 15 retrieval methods (13 lexical, a fine-tuned e5 kNN, exact-site) feed a 3-stage LightGBM cascade plus a cross-encoder feature. The answer for each S1 is a calibrated expected-F0.5 set, with no global threshold.

after completing the competition, i asked claude to make a proper video that we can use in the presentation if needed for the whole pipeline at a glance and i think rather than me rawdogging on excalidraw and handwriting latex, its better we see what we can achieve w/ good prompting + manim (thanks 3b1b).

![the whole pipeline, animated](/video/pipeline-overview.mp4 "the pipeline at a glance. no need to thank me for my goated music taste.")

## workflow setup

now this is the part where most of the participants felt the need for "better" compute.

to put it simply, yes we used big GPUs but anyone w/ a student email can get A100s on google colab runtime for small jobs. *small* is the keyword here. the idea was to delegate only gpu intensive jobs to these colab notebooks and everything locally on my macbook.

okay real specs for the HW nerds:

> MacBook Pro M5 Pro (15 CPU cores, 24 GB RAM), no local GPU work; Google Colab for GPU. No cluster.

and its silver colored mac for anyone wondering my color taste.

anyways, most of the jobs on my laptop were insanely cpu intensive so i had to think of an efficient way to delegate tasks such that i can still type on that thing.

so i added some constraints in my script that runs this whole workflow (except the part where i upload NB on colab. let us all agree on their terrible design).

- heavy jobs: 4 threads, **`nice -n 19`** (lowest priority), via `scripts/ber_heavy.sh`: a 2-slot lock (`mkdir` on `/tmp/ber_heavy.lock{,2}`, owner PID stored, stale slots of dead PIDs cleared, retry every 5 s).
- heaviest step peaked at ~6 GiB RSS, so two jobs fit in 24 GB.

as i mentioned, efficiency is the key if you are short on time. writing better scripts + proper constraints will always pay dividends.

this way i still could use my laptop to send cat videos in the group chat w/o burning my hands scrolling. moving on...

okay but how did i use colab? cause fine tuning and cross encoding aint possible for my cpu, right?

that was exactly the plan. gdrive was the middleman here. (again fk u colab)

colab did only three jobs:

- **step 6, e5 kNN** (`01_encoder_knn.ipynb`): fine-tune e5-small, embed all 24.2M records, exact per-country nearest-neighbour search.
- **step 13, cross-encoder v2** (`02_cross_encoder.ipynb`): e5-small (118M params), two fold models, A100.
- **step 13b, cross-encoder v3** (`02_cross_encoder.ipynb`): e5-base (278M params), two fold models, A100.

ps: pls refer to these steps in the diagrams below.

rough sketch of the pipeline:

![workflow diagram of the local and colab steps](/images/amazon-ml-workflow.webp "rough sketch of the pipeline")

for the nerds or if you want to know how the whole pipeline mapped around the whole problem + repo system:

![system diagram mapping the pipeline onto the problem and the repo](/images/amazon-ml-system.webp "the pipeline mapped onto the problem and the repo")

now i think this is pretty much self explanatory, i dont know if i can share my whole solution publicly as of now, so holding that off for now. but soon it'll be posted, so do wtv u want w/ this info.

## jumping the ladder

probably the most imp part of this blog (hopefully), my fav niche nonetheless. i luvv optimizing things to their best, every squeeze of another perf boost gives me a different kind of joy.

and since these are just numbers, the goal is simple: "get to the biggest number as possible". in this case, getting closest to 1 or the actual theoretical limit was the goal.

its not like our score was always #3 on the leaderboard, we started somewhere around ~200 rank as our baseline/first run. this was my first run, we had ~20 hrs left after this. yes i wish i took this challenge seriously from day1 but whatever.

our baseline run exposed the biggest bottleneck, lack of french tests in the local verifier. sole reason of local scores and public scores being vastly different.

we could measure US/India scores through our local verifiers but for France, we always had to submit it to the public LB and that costs one attempt. there are only limited attempts. so the only possible clever way was to think of a way to map these scores to the France data. with 2/3 public attempts, we had a decent idea for our French score solely. at this point, the F0.5 for French was ~94% but its not that easy to just increase this number. French was technically difficult for our pipeline, so even the tiniest gains took hours to find.

all of these gains combined + structured as a timeline:

![timeline of score gains over the 24 hours](/images/amazon-ml-timeline.webp "every gain, in order")

but these were not in a straight timeline, there were few detours and weird ideas that we dropped along the way, such as:

- e5-large cross-encoder: 13-min fine-tune per fold, AUC 0.9418 < 0.9585 for the existing blend; every blend weight lowered AUC.
- cross encoder columns in the calibrator lol, stage C already used CE
- france typo words
- LOCO feat variants
- test vs val density shift correction
- and even more, there were like 20+ ideas we had that showed no wins and some even degraded our perfs (all scored locally ofc)

i *want* to talk about this stuff in more detail but cant disclose our solution as of now, so hold your horses. it'll be posted on my [github](https://github.com/saarthak314) so yeah.

and at last, i think this challenge was an amazing exp for competitive spirit, learning new things, finding efficient solutions and much more...

to sum our journey throughout the challenge:

![the journey from rank ~200 to #3](/images/amazon-ml-journey.webp "the whole journey")




### agents used

only claude opus 5.5 on high reasoning is used throughout the time. im on max plan but it barely hit my limits. workflow was simple, i used `/goal` throughout with *A LOT* of steeerings as you can clearly tell.

for formatting thsi article, 6.1 sol was used.
