# Copyright (c) 2016-2020 Chris Cummins.
#
# clgen is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# clgen is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with clgen.  If not, see <https://www.gnu.org/licenses/>.
"""Unit tests for //deeplearning/clgen/corpuses:atomizers."""
import json
import pathlib
import tempfile

import deeplearning.clgen.errors
from deeplearning.clgen.corpuses import atomizers
from labm8.py import app
from labm8.py import bazelutil
from labm8.py import test

FLAGS = app.FLAGS

pytest_plugins = ["deeplearning.clgen.tests.fixtures"]

# The set of multichar tokens for the OpenCL programming language.
TOKEN_LISTS = json.loads(
  bazelutil.DataString("phd/deeplearning/clgen/corpuses/token_lists.json")
)

OPENCL_ATOMS = TOKEN_LISTS["opencl"]["tokens"]

# AsciiCharacterAtomizer


def test_AsciiCharacterAtomizer_FromText():
  """Test deriving an atomizer from a sequence of characters."""
  c = atomizers.AsciiCharacterAtomizer.FromText("abcabc")

  assert c.indices == [0, 1, 2]
  assert c.atoms == ["a", "b", "c"]
  assert c.vocab_size == 3


def test_AsciiCharacterAtomizer_ToFile_FromFile_equivalency():
  """Test that ToFile() and FromFile() produce the same atomizer."""
  # Create an atomizer.
  c1 = atomizers.AsciiCharacterAtomizer.FromText("abcabc")
  assert c1.indices == [0, 1, 2]
  assert c1.atoms == ["a", "b", "c"]
  assert c1.vocab_size == 3

  with tempfile.TemporaryDirectory() as d:
    # Save atomizer to file.
    c1.ToFile(pathlib.Path(d) / "atomizer")

    # Load atomizer from file.
    c2 = atomizers.AtomizerBase.FromFile(pathlib.Path(d) / "atomizer")
    assert type(c2) == atomizers.AsciiCharacterAtomizer
    assert c2.vocab == c1.vocab
    assert c2.indices == [0, 1, 2]
    assert c2.atoms == ["a", "b", "c"]
    assert c2.vocab_size == 3


def test_AsciiCharacterAtomizer_AtomizeString():
  c = atomizers.AsciiCharacterAtomizer({"a": 1, "b": 2, "c": 3})
  assert list(c.AtomizeString("abcabc")) == [1, 2, 3, 1, 2, 3]


def test_AsciiCharacterAtomizer_AtomizeString_vocab_error():
  c = atomizers.AsciiCharacterAtomizer({"a": 1, "b": 2, "c": 3})
  with test.Raises(deeplearning.clgen.errors.VocabError):
    c.AtomizeString("abcdeabc")


def test_AsciiCharacterAtomizer_DeatomizeIndices():
  c = atomizers.AsciiCharacterAtomizer({"a": 1, "b": 2, "c": 3})
  assert c.DeatomizeIndices([1, 2, 3, 1, 2, 3]) == "abcabc"

  text = """
__kernel void A(__global float* a, const int b, const double c) {
  int d = get_global_id(0);
  if (b < get_global_size(0))
    a[d] *= (float)c;
}
"""
  c = atomizers.AsciiCharacterAtomizer.FromText(text)
  assert c.DeatomizeIndices(c.AtomizeString(text)) == text


def test_AsciiCharacterAtomizer_DeatomizeIndices_error():
  c = atomizers.AsciiCharacterAtomizer({"a": 1, "b": 2, "c": 3})
  with test.Raises(deeplearning.clgen.errors.VocabError):
    c.DeatomizeIndices([1, 2, 5, 10, 0])


# GreedyAtomizer


def test_GreedyAtomizer_TokenizeString_1():
  test_vocab = {"abc": 1, "a": 2, "b": 3, "ab": 4, "c": 5, "cab": 6, " ": 7}
  test_in = "abcababbaabcabcaabccccabcabccabcccabcabc"
  test_out = [
    "abc",
    "ab",
    "ab",
    "b",
    "a",
    "abc",
    "abc",
    "a",
    "abc",
    "c",
    "c",
    "cab",
    "cab",
    "c",
    "cab",
    "c",
    "c",
    "cab",
    "cab",
    "c",
  ]
  c = atomizers.GreedyAtomizer(test_vocab)
  assert c.TokenizeString(test_in) == test_out


def test_GreedyAtomizer_TokenizeString_2():
  test_vocab = {"volatile": 0, "voletile": 1, "vo": 2, " ": 3, "l": 4}
  test_in = "volatile voletile vol "
  test_out = ["volatile", " ", "voletile", " ", "vo", "l", " "]
  c = atomizers.GreedyAtomizer(test_vocab)
  assert c.TokenizeString(test_in) == test_out


def test_GreedyAtomizer_TokenizeString_3():
  test_in = """\
__kernel void A(__global float* a, __global float* b, const int c) {
  int d = get_global_id(0);
  if (d < c) {
    a[d] = b[d] * 10.0f;
  }
}\
"""
  test_out = [
    "__kernel",
    " ",
    "void",
    " ",
    "A",
    "(",
    "__global",
    " ",
    "float",
    "*",
    " ",
    "a",
    ",",
    " ",
    "__global",
    " ",
    "float",
    "*",
    " ",
    "b",
    ",",
    " ",
    "const",
    " ",
    "int",
    " ",
    "c",
    ")",
    " ",
    "{",
    "\n",
    "  ",
    "int",
    " ",
    "d",
    " ",
    "=",
    " ",
    "get_global_id",
    "(",
    "0",
    ")",
    ";",
    "\n",
    "  ",
    "if",
    " ",
    "(",
    "d",
    " ",
    "<",
    " ",
    "c",
    ")",
    " ",
    "{",
    "\n",
    "  ",
    "  ",
    "a",
    "[",
    "d",
    "]",
    " ",
    "=",
    " ",
    "b",
    "[",
    "d",
    "]",
    " ",
    "*",
    " ",
    "1",
    "0",
    ".",
    "0",
    "f",
    ";",
    "\n",
    "  ",
    "}",
    "\n",
    "}",
  ]
  c = atomizers.GreedyAtomizer.FromText(test_in, OPENCL_ATOMS)
  assert c.TokenizeString(test_in) == test_out


def test_GreedyAtomizer_DeatomizeIndices():
  test_in = """\
__kernel void A(__global float* a, __global float* b, const int c) {
  int d = get_global_id(0);
  if (d < c) {
    a[d] = b[d] * 10.0f;
  }
}\
"""
  c = atomizers.GreedyAtomizer.FromText(test_in, OPENCL_ATOMS)
  a = c.AtomizeString(test_in)
  assert c.DeatomizeIndices(a) == test_in


def test_GreedyAtomizer_FromText():
  test_in = """\
__kernel void A(__global float* a, __global float* b, const int c) {
  int d = get_global_id(0);
  if (d < c) {
    a[d] = b[d] * 10.0f;
  }
}\
"""
  tokens = [
    "__kernel",
    " ",
    "A",
    "(",
    ")",
    "__global",
    "float",
    "*",
    "a",
    "0",
    "b",
    "const",
    "int",
    "c",
    "{",
    "}",
    "  ",
    "d",
    "get_global_id",
    ";",
    "if",
    "<",
    "[",
    "]",
    "f",
    ".",
    "1",
    "\n",
    "=",
    ",",
    "void",
  ]
  c = atomizers.GreedyAtomizer.FromText(test_in, OPENCL_ATOMS)
  assert sorted(c.atoms) == sorted(tokens)
  assert c.vocab_size == len(tokens)


if __name__ == "__main__":
  test.Main()
