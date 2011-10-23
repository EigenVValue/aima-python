"""Learn to estimate functions from examples. (Chapters 18-20)"""

from utils import *
import heapq, random

#______________________________________________________________________________

def rms_error(predictions, targets):
    return math.sqrt(ms_error(predictions, targets))

def ms_error(predictions, targets):
    return mean([(p - t)**2 for p, t in zip(predictions, targets)])

def mean_error(predictions, targets):
    return mean([abs(p - t) for p, t in zip(predictions, targets)])

def mean_boolean_error(predictions, targets):
    return mean([(p != t)   for p, t in zip(predictions, targets)])

#______________________________________________________________________________

class DataSet:
    """A data set for a machine learning problem.  It has the following fields:

    d.examples    A list of examples.  Each one is a list of attribute values.
    d.attrs       A list of integers to index into an example, so example[attr]
                  gives a value. Normally the same as range(len(d.examples[0])).
    d.attrnames   Optional list of mnemonic names for corresponding attrs.
    d.target      The attribute that a learning algorithm will try to predict.
                  By default the final attribute.
    d.inputs      The list of attrs without the target.
    d.values      A list of lists: each sublist is the set of possible
                  values for the corresponding attribute. If initially None,
                  it is computed from the known examples by self.setproblem.
                  If not None, an erroneous value raises ValueError.
    d.distance    A function from a pair of examples to a nonnegative number.
                  Should be symmetric, etc. Defaults to mean_boolean_error
                  since that can handle any field types.
    d.name        Name of the data set (for output display only).
    d.source      URL or other source where the data came from.

    Normally, you call the constructor and you're done; then you just
    access fields like d.examples and d.target and d.inputs."""

    def __init__(self, examples=None, attrs=None, attrnames=None, target=-1,
                 inputs=None, values=None, distance=mean_boolean_error,
                 name='', source='', exclude=()):
        """Accepts any of DataSet's fields.  Examples can also be a
        string or file from which to parse examples using parse_csv.
        Optional parameter: exclude, as documented in .setproblem().
        >>> DataSet(examples='1, 2, 3')
        <DataSet(): 1 examples, 3 attributes>
        """
        update(self, name=name, source=source, values=values, distance=distance)
        # Initialize .examples from string or list or data directory
        if isinstance(examples, str):
            self.examples = parse_csv(examples)
        elif examples is None:
            self.examples = parse_csv(DataFile(name+'.csv').read())
        else:
            self.examples = examples
        # Attrs are the indices of examples, unless otherwise stated.
        if not attrs and self.examples:
            attrs = range(len(self.examples[0]))
        self.attrs = attrs
        # Initialize .attrnames from string, list, or by default
        if isinstance(attrnames, str):
            self.attrnames = attrnames.split()
        else:
            self.attrnames = attrnames or attrs
        self.setproblem(target, inputs=inputs, exclude=exclude)

    def setproblem(self, target, inputs=None, exclude=()):
        """Set (or change) the target and/or inputs.
        This way, one DataSet can be used multiple ways. inputs, if specified,
        is a list of attributes, or specify exclude as a list of attributes
        to not use in inputs. Attributes can be -n .. n, or an attrname.
        Also computes the list of possible values, if that wasn't done yet."""
        self.target = self.attrnum(target)
        exclude = map(self.attrnum, exclude)
        if inputs:
            self.inputs = removeall(self.target, inputs)
        else:
            self.inputs = [a for a in self.attrs
                           if a is not self.target and a not in exclude]
        if not self.values:
            self.values = map(unique, zip(*self.examples))
        self.check_me()

    def check_me(self):
        "Check that my fields make sense."
        assert len(self.attrnames) == len(self.attrs)
        assert self.target in self.attrs
        assert self.target not in self.inputs
        assert set(self.inputs).issubset(set(self.attrs))
        map(self.check_example, self.examples)

    def add_example(self, example):
        "Add an example to the list of examples, checking it first."
        self.check_example(example)
        self.examples.append(example)

    def check_example(self, example):
        "Raise ValueError if example has any invalid values."
        if self.values:
            for a in self.attrs:
                if example[a] not in self.values[a]:
                    raise ValueError('Bad value %s for attribute %s in %s' %
                                     (example[a], self.attrnames[a], example))

    def attrnum(self, attr):
        "Returns the number used for attr, which can be a name, or -n .. n-1."
        if attr < 0:
            return len(self.attrs) + attr
        elif isinstance(attr, str):
            return self.attrnames.index(attr)
        else:
            return attr

    def sanitize(self, example):
       "Return a copy of example, with non-input attributes replaced by None."
       return [attr_i if i in self.inputs else None
               for i, attr_i in enumerate(example)]

    def __repr__(self):
        return '<DataSet(%s): %d examples, %d attributes>' % (
            self.name, len(self.examples), len(self.attrs))

#______________________________________________________________________________

def parse_csv(input, delim=','):
    r"""Input is a string consisting of lines, each line has comma-delimited
    fields.  Convert this into a list of lists.  Blank lines are skipped.
    Fields that look like numbers are converted to numbers.
    The delim defaults to ',' but '\t' and None are also reasonable values.
    >>> parse_csv('1, 2, 3 \n 0, 2, na')
    [[1, 2, 3], [0, 2, 'na']]
    """
    lines = [line for line in input.splitlines() if line.strip() is not '']
    return [map(num_or_str, line.split(delim)) for line in lines]

#______________________________________________________________________________

def PluralityLearner(dataset):
    """A very dumb algorithm: always pick the result that was most popular
    in the training data.  Makes a baseline for comparison."""
    most_popular = mode([e[dataset.target] for e in dataset.examples])
    def predict(example):
        "Always return same result: the most popular from the training set."
        return most_popular
    return predict

#______________________________________________________________________________

def NaiveBayesLearner(dataset):
    """Just count the target/attr/val occurrences.
    Count how many times each value of each input attribute occurs.
    Store count in _N[targetvalue][attr][val]. Let
    _N[targetvalue][attr][None] be the sum over all vals."""

    _N = {}
    ## Initialize to 0
    for gv in dataset.values[dataset.target]:
        _N[gv] = {}
        for attr in dataset.inputs:
            _N[gv][attr] = {}
            assert None not in dataset.values[attr]
            for val in dataset.values[attr]:
                _N[gv][attr][val] = 0
                _N[gv][attr][None] = 0
    ## Go thru examples
    for example in dataset.examples:
        Ngv = _N[example[dataset.target]]
        for attr in dataset.inputs:
            Ngv[attr][example[attr]] += 1
            Ngv[attr][None] += 1

    def predict(example):
        """Predict the target value for example. Consider each possible value,
        choose the most likely, by looking at each attribute independently."""
        possible_values = dataset.values[dataset.target]
        def class_probability(targetval):
            return product(P(targetval, a, example[a]) for a in dataset.inputs)
        return argmax(possible_values, class_probability)

    def P(targetval, attr, attrval):
        """Smooth the raw counts to give a probability estimate.
        Estimate adds 1 to numerator and len(possible vals) to denominator."""
        return ((N(targetval, attr, attrval) + 1.0) /
                (N(targetval, attr, None) + len(dataset.values[attr])))

    def N(targetval, attr, attrval):
       "Return the count in the training data of this combination."
       try:
          return _N[targetval][attr][attrval]
       except KeyError:
          return 0

    return predict

#______________________________________________________________________________

def NearestNeighborLearner(dataset, k=1):
    "k-NearestNeighbor: the k nearest neighbors vote."
    def predict(example):
        "Find the k closest, and have them vote for the best."
        best = heapq.nsmallest(k, ((dataset.distance(e, example), e)
                                   for e in dataset.examples))
        return mode([e[dataset.target] for (d, e) in best])
    return predict

#______________________________________________________________________________

class DecisionFork:
    """A fork of a decision tree holds an attribute to test, and a dict 
    of branches, one for each of the attribute's values."""

    def __init__(self, attr, attrname=None, branches=None):
        "Initialize by saying what attribute this node tests."
        update(self, attr=attr, attrname=attrname or attr,
               branches=branches or {})

    def __call__(self, example):
        "Given an example, classify it using the attribute and the branches."
        attrvalue = example[self.attr]
        return self.branches[attrvalue](example)

    def add(self, val, subtree):
        "Add a branch.  If self.attr = val, go to the given subtree."
        self.branches[val] = subtree

    def display(self, indent=0):
        name = self.attrname
        print 'Test', name
        for (val, subtree) in self.branches.items():
            print ' '*4*indent, name, '=', val, '==>',
            subtree.display(indent+1)

    def __repr__(self):
        return ('DecisionFork(%r, %r, %r)'
                % (self.attr, self.attrname, self.branches))
    
class DecisionLeaf:
    "A leaf of a decision tree holds just a result."

    def __init__(self, result):
        self.result = result

    def __call__(self, example):
        return self.result

    def display(self, indent=0):
        print 'RESULT =', self.result

    def __repr__(self):
        return repr(self.result)
    
#______________________________________________________________________________

def DecisionTreeLearner(dataset):
    "[Fig. 18.5]"

    target, values = dataset.target, dataset.values

    def decision_tree_learning(examples, attrs, parent_examples=()):
        if len(examples) == 0:
            return plurality_value(parent_examples)
        elif all_same_class(examples):
            return DecisionLeaf(examples[0][target])
        elif len(attrs) == 0:
            return plurality_value(examples)
        else:
            A = choose_attribute(attrs, examples)
            tree = DecisionFork(A, dataset.attrnames[A])
            for (v_k, exs) in split_by(A, examples):
                subtree = decision_tree_learning(
                    exs, removeall(A, attrs), examples)
                tree.add(v_k, subtree)
            return tree

    def plurality_value(examples):
        """Return the most popular target value for this set of examples.
        (If target is binary, this is the majority; otherwise plurality.)"""
        popular = argmax_random_tie(values[target],
                                    lambda v: count(target, v, examples))
        return DecisionLeaf(popular)

    def count(attr, val, examples):
        return count_if(lambda e: e[attr] == val, examples)

    def all_same_class(examples):
        "Are all these examples in the same target class?"
        class0 = examples[0][target]
        return all(e[target] == class0 for e in examples)

    def choose_attribute(attrs, examples):
        "Choose the attribute with the highest information gain."
        return argmax_random_tie(attrs,
                                 lambda a: information_gain(a, examples))

    def information_gain(attr, examples):
        def I(examples):
            return information_content([count(target, v, examples)
                                        for v in values[target]])
        N = float(len(examples))
        remainder = 0
        for (v, examples_i) in split_by(attr, examples):
            remainder += (len(examples_i) / N) * I(examples_i)
        return I(examples) - remainder

    def split_by(attr, examples):
        "Return a list of (val, examples) pairs for each val of attr."
        return [(v, [e for e in examples if e[attr] == v])
                for v in values[attr]]

    return decision_tree_learning(dataset.examples, dataset.inputs)

def information_content(values):
    "Number of bits to represent the probability distribution in values."
    # If the values do not sum to 1, normalize them to make them a Prob. Dist.
    values = removeall(0, values)
    s = float(sum(values))
    if s != 1.0: values = [v/s for v in values]
    return sum([- v * log2(v) for v in values])

#______________________________________________________________________________

### A decision list is implemented as a list of (test, value) pairs.

def DecisionListLearner(dataset):
    """[Fig. 18.11]"""

    def decision_list_learning(examples):
        if not examples:
            return [(True, No)]
        t, o, examples_t = find_examples(examples)
        if not t:
            raise Failure
        return [(t, o)] + decision_list_learning(examples - examples_t)

    def find_examples(examples):
        """Find a set of examples that all have the same outcome under
        some test. Return a tuple of the test, outcome, and examples."""
        NotImplemented

    def passes(example, test):
        "Does the example pass the test?"
        NotImplemented

    def predict(example):
        "Predict the outcome for the first passing test."
        for test, outcome in predict.decision_list:
            if passes(example, test):
                return outcome
    predict.decision_list = decision_list_learning(set(dataset.examples))

    return predict

#______________________________________________________________________________

def NeuralNetLearner(dataset, sizes):
   """Layered feed-forward network."""

   activations = map(lambda n: [0.0 for i in range(n)], sizes)
   weights = []

   def predict(example):
      NotImplemented

   return predict

class NNUnit:
   """Unit of a neural net."""
   def __init__(self):
       NotImplemented

def PerceptronLearner(dataset, sizes):
   def predict(example):
      return sum([])
   NotImplemented
#______________________________________________________________________________

def Linearlearner(dataset):
   """Fit a linear model to the data."""
   NotImplemented
#______________________________________________________________________________

def EnsembleLearner(learners):
    """Given a list of learning algorithms, have them vote."""
    def train(dataset):
        predictors = [learner(dataset) for learner in learners]
        def predict(example):
            return mode(predictor(example) for predictor in predictors)
        return predict
    return train

#_____________________________________________________________________________
# Functions for testing learners on examples

def test(predict, dataset, examples=None, verbose=0):
    "Return the proportion of the examples that are correctly predicted."
    if examples is None: examples = dataset.examples
    if len(examples) == 0: return 0.0
    right = 0.0
    for example in examples:
        desired = example[dataset.target]
        output = predict(dataset.sanitize(example))
        if output == desired:
            right += 1
            if verbose >= 2:
               print '   OK: got %s for %s' % (desired, example)
        elif verbose:
            print 'WRONG: got %s, expected %s for %s' % (
               output, desired, example)
    return right / len(examples)

def train_and_test(learner, dataset, start, end):
    """Reserve dataset.examples[start:end] for test; train on the remainder.
    Return the proportion of examples correct on the test examples."""
    examples = dataset.examples
    try:
        dataset.examples = examples[:start] + examples[end:]
        return test(learner(dataset), dataset, examples[start:end])
    finally:
        dataset.examples = examples

def cross_validation(learner, dataset, k=10, trials=1):
    """Do k-fold cross_validate and return their mean.
    That is, keep out 1/k of the examples for testing on each of k runs.
    Shuffle the examples first; If trials>1, average over several shuffles."""
    if k is None:
        k = len(dataset.examples)
    if trials > 1:
        return mean([cross_validation(learner, dataset, k, trials=1)
                     for t in range(trials)])
    else:
        n = len(dataset.examples)
        random.shuffle(dataset.examples)
        return mean([train_and_test(learner, dataset, i*(n/k), (i+1)*(n/k))
                     for i in range(k)])

def leave1out(learner, dataset):
    "Leave one out cross-validation over the dataset."
    return cross_validation(learner, dataset, k=len(dataset.examples))

def learningcurve(learner, dataset, trials=10, sizes=None):
    if sizes is None:
        sizes = range(2, len(dataset.examples)-10, 2)
    def score(learner, size):
        random.shuffle(dataset.examples)
        return train_and_test(learner, dataset, 0, size)
    return [(size, mean([score(learner, size) for t in range(trials)]))
            for size in sizes]

#______________________________________________________________________________
# The rest of this file gives datasets for machine learning problems.

orings = DataSet(name='orings', target='Distressed',
                 attrnames="Rings Distressed Temp Pressure Flightnum")


zoo = DataSet(name='zoo', target='type', exclude=['name'],
              attrnames="name hair feathers eggs milk airborne aquatic " +
              "predator toothed backbone breathes venomous fins legs tail " +
              "domestic catsize type")


iris = DataSet(name="iris", target="class",
               attrnames="sepal-len sepal-width petal-len petal-width class")

#______________________________________________________________________________
# The Restaurant example from Fig. 18.2

def RestaurantDataSet(examples=None):
    "Build a DataSet of Restaurant waiting examples. [Fig. 18.3]"
    return DataSet(name='restaurant', target='Wait', examples=examples,
                   attrnames='Alternate Bar Fri/Sat Hungry Patrons Price '
                    + 'Raining Reservation Type WaitEstimate Wait')

restaurant = RestaurantDataSet()

def T(attrname, branches):
    branches = dict((value, (child if isinstance(child, DecisionFork)
                             else DecisionLeaf(child)))
                    for value, child in branches.items())
    return DecisionFork(restaurant.attrnum(attrname), attrname, branches)

Fig[18,2] = T('Patrons',
             {'None': 'No', 'Some': 'Yes', 'Full':
              T('WaitEstimate',
                {'>60': 'No', '0-10': 'Yes',
                 '30-60':
                 T('Alternate', {'No':
                                 T('Reservation', {'Yes': 'Yes', 'No':
                                                   T('Bar', {'No':'No',
                                                             'Yes':'Yes'})}),
                                 'Yes':
                                 T('Fri/Sat', {'No': 'No', 'Yes': 'Yes'})}),
                 '10-30':
                 T('Hungry', {'No': 'Yes', 'Yes':
                           T('Alternate',
                             {'No': 'Yes', 'Yes':
                              T('Raining', {'No': 'No', 'Yes': 'Yes'})})})})})

__doc__ += """
[Fig. 18.6]
>>> random.seed(437)
>>> restaurant_tree = DecisionTreeLearner(restaurant)
>>> restaurant_tree.display()
Test Patrons
 Patrons = None ==> RESULT = No
 Patrons = Full ==> Test Hungry
     Hungry = Yes ==> Test Type
         Type = Burger ==> RESULT = Yes
         Type = Thai ==> Test Fri/Sat
             Fri/Sat = Yes ==> RESULT = Yes
             Fri/Sat = No ==> RESULT = No
         Type = French ==> RESULT = Yes
         Type = Italian ==> RESULT = No
     Hungry = No ==> RESULT = No
 Patrons = Some ==> RESULT = Yes
"""

def SyntheticRestaurant(n=20):
    "Generate a DataSet with n examples."
    def gen():
        example = map(random.choice, restaurant.values)
        example[restaurant.target] = Fig[18,2](example)
        return example
    return RestaurantDataSet([gen() for i in range(n)])

#______________________________________________________________________________
# Artificial, generated datasets.

def Majority(k, n):
    """Return a DataSet with n k-bit examples of the majority problem:
    k random bits followed by a 1 if more than half the bits are 1, else 0."""
    examples = []
    for i in range(n):
        bits = [random.choice([0, 1]) for i in range(k)]
        bits.append(int(sum(bits) > k/2))
        examples.append(bits)
    return DataSet(name="majority", examples=examples)

def Parity(k, n, name="parity"):
    """Return a DataSet with n k-bit examples of the parity problem:
    k random bits followed by a 1 if an odd number of bits are 1, else 0."""
    examples = []
    for i in range(n):
        bits = [random.choice([0, 1]) for i in range(k)]
        bits.append(sum(bits) % 2)
        examples.append(bits)
    return DataSet(name=name, examples=examples)

def Xor(n):
    """Return a DataSet with n examples of 2-input xor."""
    return Parity(2, n, name="xor")

def ContinuousXor(n):
    "2 inputs are chosen uniformly from (0.0 .. 2.0]; output is xor of ints."
    examples = []
    for i in range(n):
        x, y = [random.uniform(0.0, 2.0) for i in '12']
        examples.append([x, y, int(x) != int(y)])
    return DataSet(name="continuous xor", examples=examples)

#______________________________________________________________________________

def compare(algorithms=[PluralityLearner, NaiveBayesLearner,
                        NearestNeighborLearner, DecisionTreeLearner],
            datasets=[iris, orings, zoo, restaurant, SyntheticRestaurant(20),
                      Majority(7, 100), Parity(7, 100), Xor(100)],
            k=10, trials=1):
    """Compare various learners on various datasets using cross-validation.
    Print results as a table."""
    print_table([[a.__name__.replace('Learner','')] +
                 [cross_validation(a, d, k, trials) for d in datasets]
                 for a in algorithms],
                header=[''] + [d.name[0:7] for d in datasets], numfmt='%.2f')
