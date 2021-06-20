##################################################################################
#                Copyright 2021  Richardson Lab at Duke University
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import math
import scitbx.matrix
from scitbx.array_family import flex
from iotbx import pdb
import traceback

##################################################################################
# Internal helper function to make things that are compatible with vec3_double so
# that we can do math on them.  We need a left-hand and right-hand one so that
# we can make both version for multiplication.
def _rvec3 (xyz) :
  return scitbx.matrix.rec(xyz, (3,1))
def _lvec3 (xyz) :
  return scitbx.matrix.rec(xyz, (1,3))


##################################################################################
# This is a set of classes that implement Reduce's "Movers".  These are sets of
# atoms that have more than one potential set of locations.
#  - They may have a-priori preferences for some locations over others.
#  - They may have both coarse locations that they test and a set of fine
#    locations around each coarse location.
#  - They may have final tune-up behaviors once their final locations are selected.
#
# There are two basic types of Movers:
#  - Rotater: One or more Hydrogen atoms that have a set of orientations spinning
#    around a common axis.
#  - Flipper: A structure that has pairs of atoms that have similar densities, such
#    that flipping them across a center axis produces similar density fits.
#    They sometimes have optional hydrogen placements on some of the atoms.
#
# All Movers have the following methods, parameters, and return types:
#  - type PositionReturn: ( flex<atom> atoms, flex<flex<vec3>> positions, flex<float> preferenceEnergies,
#                           reduceOptions = None)
#     The reduceOptions is a Phil option subset.  The relevant options for each Mover
#       type below is specified in its __init__ method.
#  - PositionReturn CoarsePositions()
#     The first return lists all of the hierarchy atoms that move.
#     The second return has a vector that has some number of positions, each of
#       which is a vector the same length as the first return
#       with a vec3 position for each atom.
#     The third return has a vector of the same length as the number of positions in
#       each element of the third return; it indicates the relative favorability of
#       each possible location and should be added to the total energy by an
#       optimizer to break ties in otherwise-equivalent orientations.
#  - PositionReturn FinePositions(coarseIndex)
#     The coarseIndex indicates the index (0 for the first) of the relevant coarse
#       orientation.
#     The return values are the same as for CoarsePositions and they list potential
#       fine motions around the particular coarse position (not including the position
#       itself).  This function can be used by optimizers that wish to do heavy-weight
#       operations at a coarse resolution and then lightweight operations at a finer
#       scale; other optimizers may choose to ask for all of the fine positions and
#       append them to the coarse positions and globally optimize.
#     Note: Some Movers will return empty arrays.
#  - type FixUpReturn: ( flex<atom> atoms, flex<vec3> newPositions )
#  - FixUpReturn FixUp(coarseIndex)
#     The coarseIndex indicates the index (0 for the first) of the relevant coarse
#       orientation that was finally chosen.
#     The first return lists the atoms that should be repositioned.
#     The second return lists the new locations for each atom.
#     Note: This function may ask to modify atoms other than the ones it reported in its
#       coarse and fine position functions.  This is to attempt to optimizing bonds
#       for Flippers.  None of these depend on fine index.
#     Note: Some Movers will return empty arrays.  This indicates that no fix-up is
#       needed and the atoms are in their final positions.
#
# The caller is responsible for moving the specified atoms to their final positions,
# whether based on coarse or fine positions.  After applying the coarse or fine
# adjustment, they must call FixUp() and apply any final changes.
#
# The InteractionGraph.py script provides functions for determining which pairs of
# Movers have overlaps between movable atoms.
#

##################################################################################
# Return type from CoarsePosition() and FinePosition() calls.
class PositionReturn:
  def __init__(self, atoms, positions, preferenceEnergies):
    self.atoms = atoms
    self.positions = positions
    self.preferenceEnergies = preferenceEnergies

##################################################################################
# Return type from FixUp() calls.
class FixUpReturn:
  def __init__(self, atoms, newPositions):
    self.atoms = atoms
    self.newPositions = newPositions

##################################################################################
# A trivial Mover that returns a single result atom at a single location.
# Useful as a simple and fast test case for programs that use Movers.
# It also serves as a basic example of how to develop a new Mover.
class MoverNull:
  def __init__(self, atom, reduceOptions = None):
    self._atom = atom
  def CoarsePositions(self):
    # returns: The original atom at its original position.
    return PositionReturn([ self._atom ],
        [ [ [ self._atom.xyz[0], self._atom.xyz[1], self._atom.xyz[2] ] ] ],
        [ 0.0 ])
  def FinePositions(self, coarseIndex):
    # returns: No fine positions for any coarse position.
    return PositionReturn([], [], [])
  def FixUp(self, coarseIndex):
    # No fixups for any coarse index.
    return FixUpReturn([], [])

##################################################################################
# A base class for types of Movers that rotate one or more atoms around a single
# axis.  The derived class must determine the initial position for each atom, and
# a preferred-energies function that maps from an angle that is 0 at the initial
# location to an energy.  The range of coarse rotations is also specified, along
# with a flag telling whether fine rotations are allowed.  The coarse step size
# can also be specified, overriding the value from reduceOptions.CoarseStepDegrees.
class MoverRotater:
  def __init__(self, atoms, axis, coarseRange, coarseStepDegrees = None,
                doFineRotations = True, preferenceFunction = None,
                reduceOptions = None):
    """Constructs a Rotator, to be called by a derived class or test program but
       not usually user code.
       :param atoms: flex array of atoms that will be rotated.  These should be
       placed in one of the preferred orientations if there are any.
       : param axis: flex array with two scitbx::vec3<double> points, the first
       of which is the origin and the second is a vector pointing in the direction
       of the axis of rotation.  Positive rotations will be right-handed rotations
       around this axis.
       :param coarseRange: Range in degrees that the atoms can rotate around the axis
       from the starting position.  The range is considered closed on the negative
       end and open on the positive: [-coarseRange..coarseRange).  For example a
       range of 180 will rotate all the way around, from -180 (inclusive) to just
       slightly less than +180.
       :param coarseStepDegrees: With the default value of None, the number of
       degrees per coarse step will be determined  by the
       reduceOptions.CoarseStepDegrees or the default value of 30 if neither specifies
       the value.
       To test only two fixed orientations, doFineRotations should be set
       to False, coarseRange to 180, and coarseStepDegrees to 180.
       :param doFineRotations: Specifies whether fine rotations are allowed for
       this instance.  To test only two fixed orientations, this should be set
       to False, coarseRange to 180, and coarseStepDegrees to 180.
       :param preferenceFunction: A function that takes a floating-point
       argument in degrees of rotation about the specified axis and produces
       a floating-point energy value that is multiplied by the value of
       reduceOptions.PreferredOrientationScale and then added to the energy
       returned for this orientation by CoarsePositions() and FinePositions().
       For the default value of None, no addition is performed.
       :param reduceOptions: 
        The reduceOptions is a Phil option subset.  The relevant options for MoverRotater
          are: CoarseStepDegrees, FineStepDegrees, PreferredOrientationScale.
    """
    self._atoms = atoms
    self._axis = axis
    self._coarseRange = coarseRange
    self._doFineRotations = doFineRotations
    self._preferenceFunction = preferenceFunction
    self._reduceOptions = reduceOptions

    # Determine the coarse step size in degrees.  If it was specified in the
    # constructor, use that.  Otherwise, if it was specified in
    # reduceOptions.CoarseStepDegrees use that.  Otherwise, use a default of
    # 30 degrees.
    self._coarseStepDegrees = 30.0
    try:
      if reduceOptions.CoarseStepDegrees is not None:
        self._coarseStepDegrees = reduceOptions.CoarseStepDegrees
    except:
      pass
    if coarseStepDegrees is not None:
      self._coarseStepDegrees = coarseStepDegrees

    # Make a list of coarse angles to try based on the coarse range (inclusive
    # for negative and exclusive for positive) and the step size.  We always
    # try 0 degrees.
    # Store the angles for use by CoarsePositions() and FinePositions()
    self._coarseAngles = [0.0]
    curStep = self._coarseStepDegrees
    while curStep <= self._coarseRange:
      # The interval is closed on the left, so we place
      self._coarseAngles.append(-curStep)
      # We only place on the right if we're strictly less than because
      # the interval is open on the right.
      if curStep < self._coarseRange:
        self._coarseAngles.append(curStep)
      curStep += self._coarseStepDegrees

    # Determine the fine step size from reduceOptions.FineStepDegrees if it
    # exists; otherwise, default to 5 degrees.
    self._fineStepDegrees = 5.0
    try:
      if reduceOptions.FineStepDegrees is not None:
        self._fineStepDegrees = reduceOptions.FineStepDegrees
    except:
      pass

    # Make a list of fine angles to try to cover half the coarse step size (inclusive
    # for negative and exclusive for positive) using the fine step size.  We never
    # try +0 degrees because that is the location of the coarse rotation.
    self._fineAngles = []
    curStep = self._fineStepDegrees
    fineRange = self._coarseStepDegrees / 2
    while curStep <= fineRange:
      # The interval is closed on the left, so we place
      self._fineAngles.append(-curStep)
      # We only place on the right if we're strictly less than because
      # the interval is open on the right.
      if curStep < fineRange:
        self._fineAngles.append(curStep)
      curStep += self._fineStepDegrees

    # Determine the preference scale.  The default of 1 can be overridden by
    # a value in reduceOptions.PreferredOrientationScale.
    self._preferredOrientationScale = 1.0
    try:
      if reduceOptions.PreferredOrientationScale is not None:
        self._preferredOrientationScale = reduceOptions.PreferredOrientationScale
    except:
      pass

  def _preferencesFor(self, angles, scale):
    """Return the preference energies for the specified angles, scaled by the scale.
       :param angles: List of angles to compute the preferences at.
       :param scale: Scale factor to apply to the resulting energy function that is
       evaluated at the angles.
       :returns Energy function evaluated at the angles multiplied by the scale factor.
       If there is no energy function all entries are 0.0.
    """
    preferences = [0.0] * len(angles)
    if self._preferenceFunction is not None:
      for i, a in enumerate(angles):
        preferences[i] = self._preferenceFunction(a) * scale
    return preferences

  def _posesFor(self, angles):
    """Return the atom poses for the specified angles.
       :param angles: List of angles to compute the poses at.
       :returns List of flex.vec3_double entries, where each entry records the
       positions of all atoms when rotated about the axis by the associated angle.
       There is one entry in the list for each angle.
    """
    # @todo Turn this into a flex array of flex arrays rather than a list of flex arrays.
    poses = []
    for agl in angles:
      atoms = flex.vec3_double()
      for atm in self._atoms:
        # @todo Compute the atom vectors only once in another loop and store them for use
        # here to speed up calculations.

        # Project the atom position onto the axis, finding its closest point on the axis.
        # The position lies on a plane whose normal points along the axis vector.  The
        # point we seek is the intersection of the axis with this plane.
        # The plane equation will be the normalized axis direction vector and the offset
        # from the origin such that N.point + d = 0 defines the plane.
        # Solve for the time at which the line's ray crosses the plane and then solve for
        # the location along the line at that time.  t = - (d + (lineOrigin * planeNormal)) /
        # (lineDirection * planeNormal).  Because the line direction and normal are the
        # same, the divisor is 1.
        normal = _lvec3(self._axis[1]).normalize()
        d = -normal*atm.xyz
        t = - (d + (normal * _rvec3(self._axis[0])))
        nearPoint = _lvec3(self._axis[0]) + t * normal

        # Find the vector from the closest point towards the atom, which is its offset
        offset = _lvec3(atm.xyz) - nearPoint

        # Rotate the offset vector around the axis by the specified angle.  Add the new
        # offset to the closest point. Store this as the new location for this atom and angle.
        newOffset = offset.rotate_around_origin(_lvec3(self._axis[1]), agl*math.pi/180)
        newPos = nearPoint + newOffset
        atoms.append(newPos)
      poses.append(atoms)
    return poses;

  def CoarsePositions(self):

    # Return the atoms, coarse-angle poses, and coarse-angle preferences
    return PositionReturn(self._atoms,
      self._posesFor(self._coarseAngles),
      self._preferencesFor(self._coarseAngles, self._preferredOrientationScale))

  def FinePositions(self, coarseIndex):
    if not self._doFineRotations:
      # returns: No fine positions for any coarse position.
      return PositionReturn([], [], [])

    # We add the range of values to the coarse angle we're starting with to provide
    # the list of fine angles to try.
    angles = []
    try:
      ca = self._coarseAngles[coarseIndex]
    except Exception as e:
      raise ValueError("MoverRotater.FinePositions(): Bad coarseIndex: "+str(e))
    for fa in self._fineAngles:
      angle = fa + ca
      angles.append(angle)

    # Return the atoms and poses along with the preferences.
    return PositionReturn(self._atoms,
      self._posesFor(angles),
      self._preferencesFor(angles, self._preferredOrientationScale))

  def FixUp(self, coarseIndex):
    # No fixups for any coarse index.
    return FixUpReturn([], [])


# @todo Define each type of Mover

def Test():
  """Test function for all classes provided above.
  returns: Empty string on success, string describing the problem on failure.
  """

  # Construct a Class that will behave like the Reduce Phil data structure so that
  # we can specify the probe radius.
  class FakePhil:
    pass
  fakePhil = FakePhil()

  # Test the MoverRotater class.
  try:
    # Construct a MoverRotater with three atoms, each at +1 in Z with one at +1 in X and 0 in Y
    # and the other two at +/-1 in Y and 0 in X.  It will rotate around the Z axis with an offset
    # of -2 for the axis start location by 180 degrees with a coarse step size of 90 and a
    # preference function that always returns 1.
    atoms = []
    coords = [[ 1.0, 0.0, 1.0],
              [ 0.0, 1.0, 1.0],
              [ 0.0,-1.0, 1.0]]
    for i in range(3):
      a = pdb.hierarchy.atom()
      a.xyz = coords[i]
      atoms.append(a)
    axis = flex.vec3_double([ [ 0.0, 0.0,-2.0], [ 0.0, 0.0, 1.0] ])
    def prefFunc(x):
      return 1.0
    rot = MoverRotater(atoms,axis, 180, 90.0, True, prefFunc)

    # See if the results of each of the functions are what we expect in terms of sizes and locations
    # of atoms and preferences.  We'll use the default fine step size.
    # The first coarse rotation should be by -90 degrees, moving the first atom to (0, -1, 1)
    coarse = rot.CoarsePositions()
    if len(coarse.atoms) != 3:
      return "Movers.Test() MoverRotater basic: Expected 3 atoms for CoarsePositions, got "+str(len(coarse.atoms))
    atom0pos1 = coarse.positions[1][0]
    if (_lvec3(atom0pos1) - _lvec3([0,-1,1])).length() > 1e-5:
      return "Movers.Test() MoverRotater basic: Expected location = (0,-1,1), got "+str(atom0pos1)

    # The first fine rotation (index 0) around the second coarse index (index 1) should be to -95 degrees,
    # moving the first atom to the appropriately rotated location around the Z axis
    rad = -95 / 180 * math.pi
    x = math.cos(rad)
    y = math.sin(rad)
    z = 1
    fine = rot.FinePositions(1)
    atom0pos1 = fine.positions[0][0]
    if (_lvec3(atom0pos1) - _lvec3([x,y,z])).length() > 1e-5:
      return "Movers.Test() MoverRotater basic: Expected fine location = "+str([x,y,z])+", got "+str(atom0pos1)

    # The preference function should always return 1.
    for p in fine.preferenceEnergies:
      if p != 1:
        return "Movers.Test() MoverRotater basic: Expected preference energy = 1, got "+str(p)

    # Test None preference scale factor and a different nonzero value.
    fakePhil.PreferredOrientationScale = None
    rot = MoverRotater(atoms,axis, 180, 90.0, True, prefFunc, reduceOptions = fakePhil)
    coarse = rot.CoarsePositions()
    for p in coarse.preferenceEnergies:
      if p != 1:
        return "Movers.Test() MoverRotater None preference: Expected preference energy = 1, got "+str(p)
    fakePhil.PreferredOrientationScale = 2
    rot = MoverRotater(atoms,axis, 180, 90.0, True, prefFunc, reduceOptions = fakePhil)
    coarse = rot.CoarsePositions()
    for p in coarse.preferenceEnergies:
      if p != 2:
        return "Movers.Test() MoverRotater Phil-scaled preference: Expected preference energy = 2, got "+str(p)

    # Test None preference function and a sinusoidal one.
    rot = MoverRotater(atoms,axis, 180, 90.0, True, None)
    coarse = rot.CoarsePositions()
    for p in coarse.preferenceEnergies:
      if p != 0:
        return "Movers.Test() MoverRotater None preference function: Expected preference energy = 0, got "+str(p)
    def prefFunc2(x):
      return math.cos(x * math.pi / 180)
    rot = MoverRotater(atoms,axis, 180, 180, True, prefFunc2)
    coarse = rot.CoarsePositions()
    expected = [1, -1]
    for i,p  in enumerate(coarse.preferenceEnergies):
      val = expected[i]
      if p != val:
        return "Movers.Test() MoverRotater Sinusoidal preference function: Expected preference energy = "+str(val)+", got "+str(p)

    # Test coarseStepDegrees default behavior and setting via reduceOptions.
    rot = MoverRotater(atoms,axis, 180)
    coarse = rot.CoarsePositions()
    if len(coarse.positions) != 12:
      return "Movers.Test() MoverRotater Default coarse step: Expected 12, got "+str(len(coarse.positions))
    fakePhil.CoarseStepDegrees = 15
    rot = MoverRotater(atoms,axis, 180, reduceOptions = fakePhil)
    coarse = rot.CoarsePositions()
    if len(coarse.positions) != 24:
      return "Movers.Test() MoverRotater reduceOptions coarse step: Expected 24, got "+str(len(coarse.positions))

    # Test fineStepDegrees setting via reduceOptions.
    fakePhil.CoarseStepDegrees = None
    fakePhil.FineStepDegrees = 1
    rot = MoverRotater(atoms,axis, 180, reduceOptions = fakePhil)
    fine = rot.FinePositions(0)
    # +/- 15 degrees in 1-degree steps, but we don't do the +15 because it will be handled by the next
    # rotation up.
    if len(fine.positions) != 29:
      return "Movers.Test() MoverRotater reduceOptions fine step: Expected 29, got "+str(len(fine.positions))

    # @todo Test doFineRotations = False and 180 degree coarseStepDegrees.
  except Exception as e:
    return "Movers.Test() MoverRotater basic: Exception during test of MoverRotater: "+str(e)+"\n"+traceback.format_exc()

  # @todo Test other Mover subclasses

  return ""

  # If we're run on the command line, test our classes and functions.
if __name__ == '__main__':

  ret = Test()
  if len(ret) == 0:
    print('Success!')
  else:
    print(ret)

  assert (len(ret) == 0)
