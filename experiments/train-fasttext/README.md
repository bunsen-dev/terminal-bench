# train-fasttext

Ported from Terminal Bench's `train-fasttext` task. The agent trains a fastText
classifier on Yelp review data and must reach a target accuracy on a held-out
test set while keeping the model under a size limit.

## Data attribution

This task uses the **Yelp Review Full** dataset:

> Xiang Zhang, Junbo Zhao, Yann LeCun. "Character-level Convolutional Networks
> for Text Classification." Advances in Neural Information Processing Systems 28
> (NIPS 2015).

Source: <https://huggingface.co/datasets/Yelp/yelp_review_full>

The review text is user-generated content governed by the **Yelp Dataset Terms
of Use** (<https://www.yelp.com/dataset>), **not** by this repository's Apache-2.0
license. It is included here solely as a benchmark fixture. See the repository
root [`NOTICE`](../../NOTICE) for the third-party-data declaration.

## Data layout (and why the held-out set is not a leak)

- `Dockerfile` downloads the Yelp train/test parquets from Hugging Face **at image
  build time**; `reformat_data.py` samples 10,000 test rows (`random_state=123`)
  to form the agent's visible data under `data/`.
- `verifiers/private_test.txt` is the complementary 40,000-row held-out split
  (fastText `__label__<0-4> <text>` format). It lives in `verifiers/`, which is
  provisioned only into the **scorer** container at `/bunsen/verifiers/` — it is
  never copied into the agent's image or workspace, so the agent cannot read it.
