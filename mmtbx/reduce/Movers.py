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
import scitbx.matrix, scitbx.math
from scitbx.array_family import flex
from iotbx import pdb
import traceback

##################################################################################
def getBondedNeighborLists(atoms, bondProxies):
  """Produce a dictionary with one entry for each atom that contains a list of all of
    the atoms that are bonded to it.
    External helper function to produce a dictionary of lists that lists all bonded
    neighbors for each atom in a set of atoms.
    :param atoms: Flex aray of atoms (could be obtained using model.get_atoms()).
    :param bondProxies: Flex array of bond proxies for the atoms (could be obtained
    using model.get_restraints_manager().geometry.get_all_bond_proxies(sites_cart =
    model.get_sites_cart()) ).
    :returns a dictionary with one entry for each atom that contains a list of all of
    the atoms that are bonded to it.
  """
  atomDict = {}
  for a in atoms:
    atomDict[a.i_seq] = a
  bondedNeighbors = {}
  for a in atoms:
    bondedNeighbors[a] = []
  for bp in bondProxies:
    bondedNeighbors[atomDict[bp.i_seqs[0]]].append(atomDict[bp.i_seqs[1]])
    bondedNeighbors[atomDict[bp.i_seqs[1]]].append(atomDict[bp.i_seqs[0]])
  return bondedNeighbors

##################################################################################
# This is a set of classes that implement Reduce's "Movers".  These are sets of
# atoms that have more than one potential set of locations.
#  - They may have a-priori preferences for some locations over others.
#  - They may have both coarse locations that they test and a set of fine
#    locations around each coarse location.
#  - They may have final tune-up behaviors once their final locations are selected.
#
# There are two basic types of Movers:
#  - Rotator: One or more Hydrogen atoms that have a set of orientations spinning
#    around a common axis.
#  - Flipper: A structure that has pairs of atom groups that have similar densities, such
#    that flipping them across a center axis produces similar density fits.
#    They sometimes have optional hydrogen placements in the atom groups.
#
# All Movers have the following methods, parameters, and return types:
#  - type PositionReturn: ( flex<atom> atoms, flex<flex<vec3>> positions, flex<float> preferenceEnergies)
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
# adjustment, they must call FixUp() and apply any final changes (which may require
# removing Hydrogens).
#
# The InteractionGraph.py script provides functions for determining which pairs of
# Movers have overlaps between movable atoms.
#

##################################################################################
class PositionReturn:
  # Return type from CoarsePosition() and FinePosition() calls.
  def __init__(self, atoms, positions, preferenceEnergies):
    self.atoms = atoms
    self.positions = positions
    self.preferenceEnergies = preferenceEnergies

##################################################################################
class FixUpReturn:
  # Return type from FixUp() calls.
  def __init__(self, atoms, newPositions):
    self.atoms = atoms
    self.newPositions = newPositions

##################################################################################
class MoverNull:
  '''A trivial Mover that returns a single result atom at a single location.
     Useful as a simple and fast test case for programs that use Movers.
     It also serves as a basic example of how to develop a new Mover.
  '''
  def __init__(self, atom):
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
# @todo Consider having another constructor parameter that gives the initial rotation
# offset to place the hydrogens in a good starting location, then derived classes can
# indicate this rotation without actually having to change the positions of the Hydrogens
# that are rotating.  This offset will be added to all resulting rotations, and subtracted
# before applying the preference function.
class _MoverRotator:
  def __init__(self, atoms, axis, coarseRange, coarseStepDegrees = 30.0,
                doFineRotations = True, fineStepDegrees = 1.0,
                preferenceFunction = None, preferredOrientationScale = 1.0):
    """Constructs a Rotator, to be called by a derived class or test program but
       not usually user code.
       A base class for types of Movers that rotate one or more atoms around a single
       axis.  The derived class must determine the initial position for each atom, and
       a preferred-energies function that maps from an angle that is 0 at the initial
       location to an energy.  The range of coarse rotations is also specified, along
       with a flag telling whether fine rotations are allowed.  The coarse step size
       can also be specified, overriding the value from coarseStepDegrees.
       :param atoms: flex array of atoms that will be rotated.  These should be
       placed in one of the preferred orientations if there are any.
       :param axis: flex array with two scitbx::vec3<double> points, the first
       of which is the origin and the second is a vector pointing in the direction
       of the axis of rotation.  Positive rotations will be right-handed rotations
       around this axis.
       :param coarseRange: Range in degrees that the atoms can rotate around the axis
       from the starting position.  The range is considered closed on the negative
       end and open on the positive: [-coarseRange..coarseRange).  For example a
       range of 180 will rotate all the way around, from -180 (inclusive) to just
       slightly less than +180.
       :param coarseStepDegrees: The coarse step to take.
       To test only two fixed orientations, doFineRotations should be set
       to False, coarseRange to 180, and coarseStepDegrees to 180.
       :param doFineRotations: Specifies whether fine rotations are allowed for
       this instance.  To test only two fixed orientations, this should be set
       to False, coarseRange to 180, and coarseStepDegrees to 180.
       :param fineStepDegrees: The fine step to take.
       :param preferenceFunction: A function that takes a floating-point
       argument in degrees of rotation about the specified axis and produces
       a floating-point energy value that is multiplied by the value of
       preferredOrientationScale and then added to the energy
       returned for this orientation by CoarsePositions() and FinePositions().
       For the default value of None, no addition is performed.
       :param preferredOrientationScale: How much to scale the preferred-orientation
       energy by before adding it to the total.
    """
    self._atoms = atoms
    self._axis = axis
    self._coarseRange = coarseRange
    self._coarseStepDegrees = coarseStepDegrees
    self._doFineRotations = doFineRotations
    self._preferenceFunction = preferenceFunction
    self._fineStepDegrees = fineStepDegrees
    self._preferredOrientationScale = preferredOrientationScale

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
        atoms.append(_rotateAroundAxis(atm, self._axis, agl))
      poses.append(atoms)
    return poses;

  def CoarsePositions(self):

    # Return the atoms, coarse-angle poses, and coarse-angle preferences
    return PositionReturn(self._atoms,
      self._posesFor(self._coarseAngles),
      self._preferencesFor(self._coarseAngles, self._preferredOrientationScale))

  def FinePositions(self, coarseIndex):
    if not self._doFineRotations:
      # No fine positions for any coarse position.
      return PositionReturn([], [], [])

    # We add the range of values to the coarse angle we're starting with to provide
    # the list of fine angles to try.
    angles = []
    try:
      ca = self._coarseAngles[coarseIndex]
    except Exception as e:
      raise ValueError("MoverRotator.FinePositions(): Bad coarseIndex: "+str(e))
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

##################################################################################
class MoverSingleHydrogenRotator(_MoverRotator):
  def __init__(self, atom, bondedNeighborLists, coarseStepDegrees = 30.0,
                  fineStepDegrees = 1.0, preferredOrientationScale = 1.0):
    """ A Mover that rotates a single Hydrogen around an axis from its bonded partner
       to the single bonded partner of its partner.  This is designed for use with OH,
       SH, and SeH configurations.  For partner-partner atoms that are bonded to a
       tetrahedron, the starting orientation is aligned between two of the edges of
       the tetrahedron.  For partner-partner atoms that are bonded to two atoms, the
       starting orientation is in the plane of these atoms and the partner-partner atom.
       :param atom: Hydrogen atom that will be rotated.  It must be bonded to a single
       atom, and that atom must also be bonded to a single other atom.  NOTE: As a side
       effect, this Hydrogen is immediately rotated to lie either in the plane of the two
       friends of the partner atom or to be between two of friends if there are three.
       :param bondedNeighborLists: A dictionary that contains an entry for each atom in the
       structure that the atom from the first parameter interacts with that lists all of the
       bonded atoms.  Can be obtained by calling getBondedNeighborLists().
       :param coarseStepDegrees: The coarse step to take.
       :param fineStepDegrees: The fine step to take.
       :param preferredOrientationScale: How much to scale the preferred-orientation
       energy by before adding it to the total.
    """

    # Check the conditions to make sure we've been called with a valid atom.  This is a hydrogen with
    # a single bonded neighbor that has a single other bonded partner that has 2-3 other bonded friends.
    # Find the friends bonded to the partner besides the neighbor, which will be used to
    # determine the initial orientation for the hydrogen.
    if atom.element != "H":
      raise ValueError("MoverSingleHydrogenRotator(): Atom is not a hydrogen")
    neighbors = bondedNeighborLists[atom]
    if len(neighbors) != 1:
      raise ValueError("MoverSingleHydrogenRotator(): Atom does not have a single bonded neighbor")
    neighbor = neighbors[0]
    partners = bondedNeighborLists[neighbor]
    if len(partners) != 2:  # Me and one other
      raise ValueError("MoverSingleHydrogenRotator(): Atom does not have a single bonded neighbor's neighbor")
    partner = partners[0]
    if partner.i_seq == atom.i_seq:
      partner = partners[1]
    bonded = bondedNeighborLists[partner]
    friends = []
    for b in bonded:
      if b.i_seq != neighbor.i_seq:
        friends.append(b)

    # Determine the preference function (180 or 120) based on friends bonding structure
    # @todo Consider parameterizing the magic constant of 0.1 for the preference magnitude
    if len(friends) == 2:
      # There are two neighbors, so our function repeats every 180 degrees
      def preferenceFunction(degrees): return 0.1 + 0.1 * math.cos(degrees * (math.pi/180) * (360/180))
    elif len(friends) == 3:
      # There are three neighbors, so our function repeats every 120 degrees
      def preferenceFunction(degrees): return 0.1 + 0.1 * math.cos(degrees * (math.pi/180) * (360/120))
    else:
      raise ValueError("MoverSingleHydrogenRotator(): Atom's bonded neighbor's neighbor does not have 2-3 other bonds "+
      "it has "+str(len(friends)))

    # Determine the axis to rotate around, which starts at the partner atom and points at the neighbor.
    normal = (_rvec3(neighbor.xyz) - _rvec3(partner.xyz)).normalize()
    axis = flex.vec3_double([partner.xyz, normal])

    # Move the atom so that it is in one of the two preferred locations.  The preferred location depends on
    # whether there are two or three friends, it wants to be in the plane if there are two of them and it
    # wants to be between two edges if there are three.  It turns out that rotating it to point away from
    # one of the friends works in both of those cases.
    atom.xyz = _rotateOppositeFriend(atom, axis, partner, friends)

    # Make a list that contains just the single atom.
    atoms = [ atom ]

    # Construct our parent class, which will do all of the actual work based on our inputs.
    _MoverRotator.__init__(self, atoms, axis, 180, coarseStepDegrees = coarseStepDegrees,
      fineStepDegrees = fineStepDegrees, preferenceFunction = preferenceFunction, 
      preferredOrientationScale = preferredOrientationScale)

##################################################################################
class MoverNH3Rotator(_MoverRotator):
  def __init__(self, atom, bondedNeighborLists, coarseStepDegrees = 30.0, fineStepDegrees = 1.0,
                preferredOrientationScale = 1.0):
    """ A Mover that rotates three Hydrogens around an axis from their bonded Nitrogen neighbor
       to the single bonded partner of its partner.  This is designed for use with NH3+,
       whose partner-partner atoms are bonded to a tetrahedron (two Carbons and a Hydrogen)
       of friends.
       The starting orientation has one of the Hydrogens aligned between two of the edges of
       the tetrahedron.
       :param atom: Nitrogen atom bonded to the three Hydrogens that will be rotated.
       It must be bonded to three Hydrogens and a single other
       atom, and the other atom must be bonded to three other atoms.  NOTE: As a side
       effect, the Hydrogens are immediately rotated to lie between two of the friends.
       :param bondedNeighborLists: A dictionary that contains an entry for each atom in the
       structure that the atom from the first parameter interacts with that lists all of the
       bonded atoms.  Can be obtained by calling getBondedNeighborLists().
       the value.
       :param fineStepDegrees: The fine step to take.
       :param preferredOrientationScale: How much to scale the preferred-orientation
       energy by before adding it to the total.
    """

    # The Nitrogen is the neighbor in these calculations, making this code symmetric with the other
    # class code.
    neighbor = atom

    # Check the conditions to make sure we've been called with a valid atom.  This is a Nitrogen with
    # three hydrogens bonded and a single bonded neighbor that has 3 other bonded friends.
    # Find the friends bonded to the partner besides the neighbor, which will be used to
    # determine the initial orientation for the hydrogens.
    if neighbor.element != "N":
      raise ValueError("MoverNH3Rotator(): atom is not a Nitrogen")
    partners = bondedNeighborLists[neighbor]
    if len(partners) != 4:
      raise ValueError("MoverNH3Rotator(): atom does not have four bonded neighbors")
    hydrogens = []
    for a in partners:
      if a.element == "H":
        hydrogens.append(a)
      else:
        partner = a
    if len(hydrogens) != 3:
      raise ValueError("MoverNH3Rotator(): atom does not have three bonded hydrogens")
    bonded = bondedNeighborLists[partner]
    friends = []
    for b in bonded:
      if b.i_seq != neighbor.i_seq:
        friends.append(b)
    if len(friends) != 3:
      raise ValueError("MoverNH3Rotator(): Partner does not have three bonded friends")

    # Set the preference function to like 120-degree rotations away from the starting location.
    # @todo Consider parameterizing the magic constant of 0.1 for the preference magnitude
    # (for example, we might use preferredOrientationScale for this and not set a separate one?)
    def preferenceFunction(degrees): return 0.1 + 0.1 * math.cos(degrees * (math.pi/180) * (360/120))

    # Determine the axis to rotate around, which starts at the partner and points at the neighbor.
    normal = (_rvec3(neighbor.xyz) - _rvec3(partner.xyz)).normalize()
    axis = flex.vec3_double([partner.xyz, normal])

    # Move the Hydrogens so that they are in one of the preferred locations by rotating one of them to
    # point away from one of the friends.  The other two are located at +120 and -120 degrees rotated
    # around the axis from the first.
    hydrogens[0].xyz = _rotateOppositeFriend(hydrogens[0], axis, partner, friends)
    hydrogens[1].xyz = _rotateAroundAxis(hydrogens[0], axis, 120)
    hydrogens[2].xyz = _rotateAroundAxis(hydrogens[0], axis, -120)

    # Construct our parent class, which will do all of the actual work based on our inputs.
    _MoverRotator.__init__(self, hydrogens, axis, 180, coarseStepDegrees,
      fineStepDegrees = fineStepDegrees, preferenceFunction = preferenceFunction,
      preferredOrientationScale = preferredOrientationScale)

##################################################################################
class MoverAromaticMethylRotator(_MoverRotator):
  def __init__(self, atom, bondedNeighborLists):
    """ A Mover that rotates three Hydrogens around an axis from their bonded Carbon neighbor
       to the single bonded partner of its partner.  This is designed for use with Aromatic
       CH3 (Methly) groups, whose partner-partner atoms are bonded to an aromatic ring, having
       two friends.
       The starting orientation has one of the Hydrogens pointing away from the plane of the ring.
       The only other preferred orientation is having that hydrogen point out the other side
       of the ring, so we only do 180-degree coarse and no fine rotation.
       :param atom: Carbon atom bonded to the three Hydrogens that will be rotated.
       It must be bonded to three Hydrogens and a single other
       atom, and the other atom must be bonded to two other atoms.  NOTE: As a side
       effect, the Hydrogens are immediately rotated to lie perpendicular to the friends.
       :param bondedNeighborLists: A dictionary that contains an entry for each atom in the
       structure that the atom from the first parameter interacts with that lists all of the
       bonded atoms.  Can be obtained by calling getBondedNeighborLists().
    """

    # The Carbon is the neighbor in these calculations, making this code symmetric with the other
    # class code.
    neighbor = atom

    # Check the conditions to make sure we've been called with a valid atom.  This is a Carbon with
    # three hydrogens bonded and a single bonded neighbor that has 2 other bonded friends.
    # Find the friends bonded to the partner besides the neighbor, which will be used to
    # determine the initial orientation for the hydrogens.
    if neighbor.element != "C":
      raise ValueError("MoverAromaticMethylRotator(): atom is not a Carbon")
    partners = bondedNeighborLists[neighbor]
    if len(partners) != 4:
      raise ValueError("MoverAromaticMethylRotator(): atom does not have four bonded neighbors")
    hydrogens = []
    for a in partners:
      if a.element == "H":
        hydrogens.append(a)
      else:
        partner = a
    if len(hydrogens) != 3:
      raise ValueError("MoverAromaticMethylRotator(): atom does not have three bonded hydrogens")
    bonded = bondedNeighborLists[partner]
    friends = []
    for b in bonded:
      if b.i_seq != neighbor.i_seq:
        friends.append(b)
    if len(friends) != 2:
      raise ValueError("MoverAromaticMethylRotator(): Partner does not have two bonded friends")

    # Determine the axis to rotate around, which starts at the partner and points at the neighbor.
    normal = (_rvec3(neighbor.xyz) - _rvec3(partner.xyz)).normalize()
    axis = flex.vec3_double([partner.xyz, normal])

    # Move the Hydrogens so that they are in one of the preferred locations by rotating one of them to
    # point away from one of the friends and then rotating it 90 degrees.  The other two are located
    # at +120 and -120 degrees rotated around the axis from the first.
    hydrogens[0].xyz = _rotateOppositeFriend(hydrogens[0], axis, partner, friends)
    hydrogens[0].xyz = _rotateAroundAxis(hydrogens[0], axis, 90)
    hydrogens[1].xyz = _rotateAroundAxis(hydrogens[0], axis, 120)
    hydrogens[2].xyz = _rotateAroundAxis(hydrogens[0], axis, -120)

    # Construct our parent class, which will do all of the actual work based on our inputs.
    # We have a coarse step size of 180 degrees and a range of 180 degrees and do not
    # allow fine rotations.
    _MoverRotator.__init__(self, hydrogens, axis, 180, 180, doFineRotations = False)

##################################################################################
class MoverTetrahedralMethylRotator(_MoverRotator):
  def __init__(self, atom, bondedNeighborLists, coarseStepDegrees = 30.0,
                  fineStepDegrees = 1.0, preferredOrientationScale = 1.0):
    """ A Mover that rotates three Hydrogens around an axis from their bonded Carbon neighbor
       to the single bonded partner of its partner.  This is designed for use with tetrahedral
       partners whose partner-partner atoms are bonded to three friends.
       The starting orientation has the Hydrogens pointing between the side of the tetrahedron.
       It can rotate to any angle to optimize for hydrogen bonds.
       Note: Reduce does not normally rotate these groups because it is not worth the computational
       cost to do so (and because this can mask mis-placed atoms by forming spurious hydrogen
       bonds), but it will construct them so that they will be aligned staggered to the
       tetrahedron.
       @todo Construct these in Reduce so that they will be staggered but do not optimize them.
       :param atom: Carbon atom bonded to the three Hydrogens that will be rotated.
       It must be bonded to three Hydrogens and a single other
       atom, and the other atom must be bonded to three other atoms.  NOTE: As a side
       effect, the Hydrogens are immediately rotated to lie staggered.
       :param bondedNeighborLists: A dictionary that contains an entry for each atom in the
       structure that the atom from the first parameter interacts with that lists all of the
       bonded atoms.  Can be obtained by calling getBondedNeighborLists().
       :param coarseStepDegrees: The coarse step to take.
       :param fineStepDegrees: The fine step to take.
       :param preferredOrientationScale: How much to scale the preferred-orientation
       energy by before adding it to the total.
    """

    # The Carbon is the neighbor in these calculations, making this code symmetric with the other
    # class code.
    neighbor = atom

    # Check the conditions to make sure we've been called with a valid atom.  This is a Carbon with
    # three hydrogens bonded and a single bonded neighbor that has 2 other bonded friends.
    # Find the friends bonded to the partner besides the neighbor, which will be used to
    # determine the initial orientation for the hydrogens.
    if neighbor.element != "C":
      raise ValueError("MoverTetrahedralMethylRotator(): atom is not a Carbon")
    partners = bondedNeighborLists[neighbor]
    if len(partners) != 4:
      raise ValueError("MoverTetrahedralMethylRotator(): atom does not have four bonded neighbors")
    hydrogens = []
    for a in partners:
      if a.element == "H":
        hydrogens.append(a)
      else:
        partner = a
    if len(hydrogens) != 3:
      raise ValueError("MoverTetrahedralMethylRotator(): atom does not have three bonded hydrogens")
    bonded = bondedNeighborLists[partner]
    friends = []
    for b in bonded:
      if b.i_seq != neighbor.i_seq:
        friends.append(b)
    if len(friends) != 3:
      raise ValueError("MoverTetrahedralMethylRotator(): Partner does not have two bonded friends")

    # Determine the axis to rotate around, which starts at the partner and points at the neighbor.
    normal = (_rvec3(neighbor.xyz) - _rvec3(partner.xyz)).normalize()
    axis = flex.vec3_double([partner.xyz, normal])

    # Move the Hydrogens so that they are in one of the preferred locations by rotating one of them to
    # point away from one of the friends.  The other two are located at +120 and -120 degrees rotated
    # around the axis from the first.
    hydrogens[0].xyz = _rotateOppositeFriend(hydrogens[0], axis, partner, friends)
    hydrogens[1].xyz = _rotateAroundAxis(hydrogens[0], axis, 120)
    hydrogens[2].xyz = _rotateAroundAxis(hydrogens[0], axis, -120)

    # Set the preference function to like 120-degree rotations away from the starting location.
    # @todo Consider parameterizing the magic constant of 0.1 for the preference magnitude
    def preferenceFunction(degrees): return 0.1 + 0.1 * math.cos(degrees * (math.pi/180) * (360/120))

    # Construct our parent class, which will do all of the actual work based on our inputs.
    # We have a coarse step size of 180 degrees and a range of 180 degrees and do not
    # allow fine rotations.
    _MoverRotator.__init__(self, hydrogens, axis, 180, fineStepDegrees = fineStepDegrees,
      preferenceFunction = preferenceFunction,
      preferredOrientationScale = preferredOrientationScale)

##################################################################################
class MoverNH2Flip:
  def __init__(self, nh2Atom, bondedNeighborLists):
    """Constructs a Mover that will handle flipping an NH2 with an O, both of which
       are attached to the same Carbon atom (and each of which has no other bonds).
       This Mover uses a simple swap of the center positions of the heavy atoms (with
       repositioning of the Hydrogens to lie in the plane with the other three atoms)
       for its testing, but during FixUp it adjusts the bond lengths of the Oxygen
       and the Nitrogen; per Protein Science Vol 27:293-315.
       This handles flips for Asn and Gln.
       :param nh2Atom: Nitrogen atom that is attached to two Hydrogens.
    """

    # The Nitrogen is the neighbor in these calculations, making this code symmetric with the other
    # class code.
    neighbor = nh2Atom

    # Verify that we've been run on a valid structure and get a list of all of the
    # atoms that we will be moving.
    if neighbor.element != "N":
      raise ValueError("MoverNH2Flip(): nh2Atom is not a Nitrogen")
    partners = bondedNeighborLists[neighbor]
    if len(partners) != 3:
      raise ValueError("MoverNH2Flip(): nh2Atom does not have three bonded neighbors")
    hydrogens = []
    for a in partners:
      if a.element == "H":
        hydrogens.append(a)
      else:
        partner = a
    if len(hydrogens) != 2:
      raise ValueError("MoverNH2Flip(): nh2Atom does not have two bonded hydrogens")
    bonded = bondedNeighborLists[partner]
    oyxgen = None
    alphaCarbon = None
    for b in bonded:
      if b.element == "O":
        oxygen = b
      if b.element == "C":
        alphaCarbon = b
    if alphaCarbon is None:
      raise ValueError("MoverNH2Flip(): Partner does not have bonded (alpha) Carbon friend")
    if oxygen is None:
      raise ValueError("MoverNH2Flip(): Partner does not have bonded oxygen friend")
    if len(bondedNeighborLists[oxygen]) != 1:
      raise ValueError("MoverNH2Flip(): Oxygen has more than one bonded neighbor")
    self._atoms = [ hydrogens[0], hydrogens[1], neighbor, partner, oxygen ]

    #########################
    # Compute the new positions for the Hydrogens such that they are at the same distance from
    # the Oxygen as one of them is from the Nitrogen and located at +/-120 degrees from the
    # Carbon-Oxygen bond in the plane of the Nitrogen, Carbon, and Oxygen.
    cToO = _lvec3(oxygen.xyz) - _lvec3(partner.xyz)
    nToO = _rvec3(neighbor.xyz) - _rvec3(partner.xyz)

    # Normal to the plane containing Nitrogen, Carbon, and Oxygen
    normal = _lvec3(scitbx.matrix.cross_product_matrix(cToO) * nToO).normalize()

    hBondLen = (_rvec3(hydrogens[0].xyz) - _rvec3(neighbor.xyz)).length()
    newH0 = _lvec3(oxygen.xyz) + ((-cToO.normalize()) * hBondLen).rotate_around_origin(normal, 120 * math.pi/180)
    newH1 = _lvec3(oxygen.xyz) + ((-cToO.normalize()) * hBondLen).rotate_around_origin(normal,-120 * math.pi/180)

    #########################
    # Compute the list of positions for all of the atoms. This consists of the original
    # location and the flipped location where we swap the locations of the two heavy atoms
    # and bring the Hydrogens along for the ride.

    self._coarsePositions = [
        [hydrogens[0].xyz, hydrogens[1].xyz, neighbor.xyz, partner.xyz, oxygen.xyz],
        [newH0,            newH1,           oxygen.xyz,   partner.xyz, neighbor.xyz]
      ]

    #########################
    # Compute the list of Fixup returns.
    # The algorithm is described in Protein Science Vol 27:293-315.  It is
    # implemented in FlipMemo::RotHingeDock_Flip() in the original Reduce C++ code,
    # where the partner is a Carbon and its other neighbor is the alpha Carbon.
    #  A) Rotate the movable atoms around the Carbon-alphaCarbon vector by 180 degrees.
    #  B) Hinge the movable atoms around the Carbon to place them back into the
    #     plane that they were originally located in using the axis of least
    #     rotation that passed through the Carbon.
    #  C) Rotate the atoms around the alphaCarbon, aligning the O and
    #     N atoms with their original locations as much as possible.  This is
    #     done in two steps: 1) Rotating around the shortest axis to make the
    #     Oxygen lie on the original vector from the alphaCarbon to the original Nitrogen.
    #     2) Rotating around the alphaCarbon-to-old-Nitrogen (new Oxygen) vector to align the plane
    #     containing the alphaCarbon, new and old Nitrogen with the plane
    #     containing the alphaCarbon, the original Oxygen and the original Nitrogen
    #     (making the dihedral angle new Nitrogen, alphaCarbon, old Nitrogen, old
    #     Oxygen be 0).
    nitrogen = nh2Atom
    carbon = partner

    # A) Rotate the movable atoms by 180 degrees
    movable = [hydrogens[0].xyz, hydrogens[1].xyz, nitrogen.xyz, carbon.xyz, oxygen.xyz]
    normal = (_rvec3(alphaCarbon.xyz) - _rvec3(carbon.xyz)).normalize()
    axis = flex.vec3_double([carbon.xyz, normal])
    for i in range(len(movable)):
      movable[i] = _rotateAroundAxis(movable[i], axis, 180)

    # B) Hinge the movable atoms around the Carbon.
    # Solve for the planes containing the old and new atoms and then the vector
    # that these planes intersect at (cross product).
    # The 

    cToO = _lvec3(oxygen.xyz) - _lvec3(carbon.xyz)
    nToO = _rvec3(nitrogen.xyz) - _rvec3(carbon.xyz)
    oldNormal = (scitbx.matrix.cross_product_matrix(cToO) * nToO).normalize()

    # Flip the order here because we've rotated 180 degrees
    newNToO = _lvec3(movable[2]) - _lvec3(movable[3])
    newCToO = _rvec3(movable[4]) - _rvec3(movable[3])
    newNormal = (scitbx.matrix.cross_product_matrix(newNToO) * newCToO).normalize()

    # If we don't need to rotate, we'll get a zero-length vector
    hinge = scitbx.matrix.cross_product_matrix(_lvec3(oldNormal))*_rvec3(newNormal)
    if hinge.length() > 0:
      hinge = hinge.normalize()
      axis = flex.vec3_double([carbon.xyz, hinge])
      degrees = 180/math.pi * math.acos((_lvec3(oldNormal)*_rvec3(newNormal))[0])
      for i in range(len(movable)):
        # Rotate in the opposite direction, taking the new back to the old.
        movable[i] = _rotateAroundAxis(_rvec3(movable[i]), axis, -degrees)

    # C) Rotate the atoms around the alphaCarbon
    #  1) Oxygen to alphaCarbon<-->original Nitrogen line
    aToNewO = _lvec3(movable[4]) - _lvec3(alphaCarbon.xyz)
    aToOldN = _rvec3(nitrogen.xyz) - _rvec3(alphaCarbon.xyz)
    # If we don't need to rotate, we'll get a zero-length vector
    normal = scitbx.matrix.cross_product_matrix(aToNewO) * aToOldN
    if normal.length() > 0:
      normal = normal.normalize()
      axis = flex.vec3_double([alphaCarbon.xyz, normal])
      degrees = 180/math.pi * math.acos((_lvec3(aToOldN.normalize())*_rvec3(aToNewO.normalize()))[0])
      for i in range(len(movable)):
        # Rotate in the opposite direction, taking the new back to the old.
        movable[i] = _rotateAroundAxis(_rvec3(movable[i]), axis, -degrees)

    #  2) Oxygen to the proper plane.
    sites = flex.vec3_double([ movable[2], alphaCarbon.xyz, nitrogen.xyz, oxygen.xyz ])
    degrees = scitbx.math.dihedral_angle(sites=sites, deg=True)
    hinge = _rvec3(alphaCarbon.xyz) - _rvec3(nitrogen.xyz)
    if hinge.length() > 0:
      hinge = hinge.normalize()
      axis = flex.vec3_double([alphaCarbon.xyz, hinge])
      for i in range(len(movable)):
        # Rotate in the opposite direction, taking the new back to the old.
        movable[i] = _rotateAroundAxis(_rvec3(movable[i]), axis, -degrees)

    # No fix-up for coarse position 0, do the above adjustment for position 1
    self._fixUpPositions = [ [], movable ]
    
  def CoarsePositions(self):
    # returns: The two possible coarse positions with 0 energy offset for either.
    return PositionReturn(self._atoms, self._coarsePositions, [0.0, 0.0])

  def FinePositions(self, coarseIndex):
    # returns: No fine positions for any coarse position.
    return PositionReturn([], [], [])

  def FixUp(self, coarseIndex):
    # Return the appropriate fixup
    return FixUpReturn(self._atoms, self._fixUpPositions[coarseIndex])

##################################################################################
# @todo Define each type of Mover

##################################################################################
# Test function to verify that all Movers behave properly.

def Test():
  """Test function for all classes provided above.
  :returns Empty string on success, string describing the problem on failure.
  :returns Empty string on success, string describing the problem on failure.
  """

  # Test the _MoverRotator class.
  try:
    # Construct a _MoverRotator with three atoms, each at +1 in Z with one at +1 in X and 0 in Y
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
    rot = _MoverRotator(atoms,axis, 180, 90.0, True, preferenceFunction = prefFunc)

    # See if the results of each of the functions are what we expect in terms of sizes and locations
    # of atoms and preferences.  We'll use the default fine step size.
    # The first coarse rotation should be by -90 degrees, moving the first atom to (0, -1, 1)
    coarse = rot.CoarsePositions()
    if len(coarse.atoms) != 3:
      return "Movers.Test() _MoverRotator basic: Expected 3 atoms for CoarsePositions, got "+str(len(coarse.atoms))
    atom0pos1 = coarse.positions[1][0]
    if (_lvec3(atom0pos1) - _lvec3([0,-1,1])).length() > 1e-5:
      return "Movers.Test() _MoverRotator basic: Expected location = (0,-1,1), got "+str(atom0pos1)

    # The first fine rotation (index 0) around the second coarse index (index 1) should be to -91 degrees,
    # moving the first atom to the appropriately rotated location around the Z axis
    rad = -91 / 180 * math.pi
    x = math.cos(rad)
    y = math.sin(rad)
    z = 1
    fine = rot.FinePositions(1)
    atom0pos1 = fine.positions[0][0]
    if (_lvec3(atom0pos1) - _lvec3([x,y,z])).length() > 1e-5:
      return "Movers.Test() _MoverRotator basic: Expected fine location = "+str([x,y,z])+", got "+str(atom0pos1)

    # The preference function should always return 1.
    for p in fine.preferenceEnergies:
      if p != 1:
        return "Movers.Test() _MoverRotator basic: Expected preference energy = 1, got "+str(p)

    # Test different preference scale value.
    rot = _MoverRotator(atoms,axis, 180, 90.0, True, preferenceFunction = prefFunc, preferredOrientationScale = 2)
    coarse = rot.CoarsePositions()
    for p in coarse.preferenceEnergies:
      if p != 2:
        return "Movers.Test() _MoverRotator Scaled preference: Expected preference energy = 2, got "+str(p)

    # Test None preference function and a sinusoidal one.
    rot = _MoverRotator(atoms,axis, 180, 90.0, True, preferenceFunction = None)
    coarse = rot.CoarsePositions()
    for p in coarse.preferenceEnergies:
      if p != 0:
        return "Movers.Test() _MoverRotator None preference function: Expected preference energy = 0, got "+str(p)
    def prefFunc2(x):
      return math.cos(x * math.pi / 180)
    rot = _MoverRotator(atoms,axis, 180, 180, True, preferenceFunction = prefFunc2)
    coarse = rot.CoarsePositions()
    expected = [1, -1]
    for i,p  in enumerate(coarse.preferenceEnergies):
      val = expected[i]
      if p != val:
        return "Movers.Test() _MoverRotator Sinusoidal preference function: Expected preference energy = "+str(val)+", got "+str(p)

    # Test coarseStepDegrees default behavior.
    rot = _MoverRotator(atoms,axis, 180)
    coarse = rot.CoarsePositions()
    if len(coarse.positions) != 12:
      return "Movers.Test() _MoverRotator Default coarse step: Expected 12, got "+str(len(coarse.positions))

    # Test fineStepDegrees setting.
    rot = _MoverRotator(atoms,axis, 180, fineStepDegrees = 2)
    fine = rot.FinePositions(0)
    # +/- 15 degrees in 1-degree steps, but we don't do the +15 because it will be handled by the next
    # rotation up.
    if len(fine.positions) != 14:
      return "Movers.Test() _MoverRotator setting fine step: Expected 14, got "+str(len(fine.positions))

    # Test doFineRotations = False and 180 degree coarseStepDegrees.
    rot = _MoverRotator(atoms,axis, 180, 180, False)
    coarse = rot.CoarsePositions()
    if len(coarse.positions) != 2:
      return "Movers.Test() _MoverRotator 180 coarse steps: Expected 2, got "+str(len(coarse.positions))
    fine = rot.FinePositions(0)
    if len(fine.positions) != 0:
      return "Movers.Test() _MoverRotator 180 coarse steps: Expected 0, got "+str(len(fine.positions))

  except Exception as e:
    return "Movers.Test() _MoverRotator basic: Exception during test of _MoverRotator: "+str(e)+"\n"+traceback.format_exc()

  # Test the MoverSingleHydrogenRotator class.
  try:
    # Construct a MoverSingleHydrogenRotator that has an atom that starts out at 45 degrees around Z
    # that is bonded to a neighbor and partner that are vertical and then partner is bonded to two
    # friends that are in the Y=0 plane.  This should cause us to get the atom rotated to lie in
    # the Y=0 plane at a distance of sqrt(2) and a fitness function that prefers the orientations
    # that are in this plane.
    h = pdb.hierarchy.atom()
    h.element = "H"
    h.xyz = [ 1.0, 1.0, 1.0 ]

    n = pdb.hierarchy.atom()
    n.xyz = [ 0.0, 0.0, 0.0 ]

    p = pdb.hierarchy.atom()
    p.xyz = [ 0.0, 0.0,-1.0 ]

    f1 = pdb.hierarchy.atom()
    f1.xyz = [ 1.0, 0.0,-2.0 ]

    f2 = pdb.hierarchy.atom()
    f2.xyz = [-1.0, 0.0,-2.0 ]

    # Build the hierarchy so we can reset the i_seq values.
    ag = pdb.hierarchy.atom_group()
    ag.append_atom(h)
    ag.append_atom(n)
    ag.append_atom(p)
    ag.append_atom(f1)
    ag.append_atom(f2)
    rg = pdb.hierarchy.residue_group()
    rg.append_atom_group(ag)
    c = pdb.hierarchy.chain()
    c.append_residue_group(rg)
    m = pdb.hierarchy.model()
    m.append_chain(c)
    m.atoms().reset_i_seq()

    bondedNeighborLists = {}
    bondedNeighborLists[h] = [ n ]
    bondedNeighborLists[n] = [ h, p ]
    bondedNeighborLists[p] = [ n, f1, f2 ]
    bondedNeighborLists[f1] = [ p ]
    bondedNeighborLists[f2] = [ p ]

    mover = MoverSingleHydrogenRotator(h, bondedNeighborLists)

    # Check for hydrogen rotated into Y=0 plane at a distance of sqrt(2) from Z axis
    if h.xyz[2] != 1 or abs(abs(h.xyz[0])-math.sqrt(2)) > 1e-5:
      return "Movers.Test() MoverSingleHydrogenRotator pair: bad H placement"

    # Check fitness function preferring 0 and 180 rotations
    zero = mover._preferenceFunction(0)
    ninety = mover._preferenceFunction(90)
    oneEighty = mover._preferenceFunction(180)
    if abs(zero - oneEighty) > 1e-5:
      return "Movers.Test() MoverSingleHydrogenRotator pair: bad preference function"
    if zero - ninety < 1e-5:
      return "Movers.Test() MoverSingleHydrogenRotator pair: bad preference function"

  except Exception as e:
    return "Movers.Test() MoverSingleHydrogenRotator pair: Exception during test: "+str(e)+"\n"+traceback.format_exc()

  try:
    # Construct a MoverSingleHydrogenRotator that has an atom that starts out at 45 degrees around Z
    # that is bonded to a neighbor and partner that are vertical and then partner is bonded to three
    # friends one of which is on the +X axis and the other two are +/-120 away from it.
    # This should cause us to get the atom rotated to be between two of the friends and a fitness
    # function that prefers its location and +/-120 degrees from it.
    h = pdb.hierarchy.atom()
    h.element = "H"
    h.xyz = [ 1.0, 1.0, 1.0 ]

    n = pdb.hierarchy.atom()
    n.xyz = [ 0.0, 0.0, 0.0 ]

    p = pdb.hierarchy.atom()
    p.xyz = [ 0.0, 0.0,-1.0 ]

    f1 = pdb.hierarchy.atom()
    f1.xyz = [ 1.0, 0.0,-2.0 ]

    f2 = pdb.hierarchy.atom()
    f2.xyz = _rotateAroundAxis(f1, axis, -120)

    f3 = pdb.hierarchy.atom()
    f3.xyz = _rotateAroundAxis(f1, axis, 120)

    # Build the hierarchy so we can reset the i_seq values.
    ag = pdb.hierarchy.atom_group()
    ag.append_atom(h)
    ag.append_atom(n)
    ag.append_atom(p)
    ag.append_atom(f1)
    ag.append_atom(f2)
    ag.append_atom(f3)
    rg = pdb.hierarchy.residue_group()
    rg.append_atom_group(ag)
    c = pdb.hierarchy.chain()
    c.append_residue_group(rg)
    m = pdb.hierarchy.model()
    m.append_chain(c)
    m.atoms().reset_i_seq()

    bondedNeighborLists = {}
    bondedNeighborLists[h] = [ n ]
    bondedNeighborLists[n] = [ h, p ]
    bondedNeighborLists[p] = [ n, f1, f2, f3 ]
    bondedNeighborLists[f1] = [ p ]
    bondedNeighborLists[f2] = [ p ]
    bondedNeighborLists[f3] = [ p ]

    mover = MoverSingleHydrogenRotator(h, bondedNeighborLists)

    # Check for a hydrogen on the -X axis at a distance of sqrt(2) from Z axis,
    # or +/-120 from there.
    angles = [0, 120, -120]
    angle = None
    for a in angles:
      rotated = _rotateAroundAxis(h, axis, a)
      if rotated[2] == 1 and rotated[0]+math.sqrt(2) < 1e-5:
        angle = a
    if angle == None:
      return "Movers.Test() MoverSingleHydrogenRotator triple: bad H placement"

    # Check fitness function preferring 180 and +/- 120 from there rotations away from
    # the angle away from 180 degrees.
    zero = mover._preferenceFunction(angle+0)
    oneEighty = mover._preferenceFunction(angle+180)
    off1 = mover._preferenceFunction(angle+180+120)
    off2 = mover._preferenceFunction(angle+180-120)
    if abs(off1 - oneEighty) > 1e-5:
      return "Movers.Test() MoverSingleHydrogenRotator triple: bad preference function"
    if abs(off2 - oneEighty) > 1e-5:
      return "Movers.Test() MoverSingleHydrogenRotator triple: bad preference function"
    if zero - oneEighty < 1e-5:
      return "Movers.Test() MoverSingleHydrogenRotator triple: bad preference function"

  except Exception as e:
    return "Movers.Test() MoverSingleHydrogenRotator triple: Exception during test: "+str(e)+"\n"+traceback.format_exc()

  # Test the MoverNH3Rotator class.
  try:
    # Construct a MoverNH3Rotator that has one hydrogen start out at 45 degrees around Z and the
    # other two at +/-120 degrees from that one.
    # They are bonded to a Nitrogen and partner that are vertical and then partner is bonded to three
    # friends with one on the +X axis and the others +/-120.  This should cause us to get the hydrogens at
    # 180 and 120 away from that and a fitness function that prefers the orientations 120 degrees
    # apart.
    axis = flex.vec3_double([ [0,0,0], [0,0,1] ])
    h1 = pdb.hierarchy.atom()
    h1.element = "H"
    h1.xyz = [ 1.0, 1.0, 1.0 ]

    h2 = pdb.hierarchy.atom()
    h2.element = "H"
    h2.xyz = _rotateAroundAxis(h1, axis, -120)

    h3 = pdb.hierarchy.atom()
    h3.element = "H"
    h3.xyz = _rotateAroundAxis(h1, axis, 120)

    n = pdb.hierarchy.atom()
    n.element = "N"
    n.xyz = [ 0.0, 0.0, 0.0 ]

    p = pdb.hierarchy.atom()
    p.xyz = [ 0.0, 0.0,-1.0 ]

    f1 = pdb.hierarchy.atom()
    f1.xyz = [ 1.0, 0.0,-2.0 ]

    f2 = pdb.hierarchy.atom()
    f2.xyz = _rotateAroundAxis(f1, axis, -120)

    f3 = pdb.hierarchy.atom()
    f3.xyz = _rotateAroundAxis(f1, axis, 120)

    # Build the hierarchy so we can reset the i_seq values.
    ag = pdb.hierarchy.atom_group()
    ag.append_atom(h1)
    ag.append_atom(h2)
    ag.append_atom(h3)
    ag.append_atom(n)
    ag.append_atom(p)
    ag.append_atom(f1)
    ag.append_atom(f2)
    ag.append_atom(f3)
    rg = pdb.hierarchy.residue_group()
    rg.append_atom_group(ag)
    c = pdb.hierarchy.chain()
    c.append_residue_group(rg)
    m = pdb.hierarchy.model()
    m.append_chain(c)
    m.atoms().reset_i_seq()

    bondedNeighborLists = {}
    bondedNeighborLists[h1] = [ n ]
    bondedNeighborLists[h2] = [ n ]
    bondedNeighborLists[h3] = [ n ]
    bondedNeighborLists[n] = [ h1, h2, h3, p ]
    bondedNeighborLists[p] = [ n, f1, f2, f3 ]
    bondedNeighborLists[f1] = [ p ]
    bondedNeighborLists[f2] = [ p ]
    bondedNeighborLists[f3] = [ p ]

    mover = MoverNH3Rotator(n, bondedNeighborLists)

    # Check for a hydrogen on the -X axis at a distance of sqrt(2) from Z axis
    found = False
    for h in [h1, h2, h3]:
      if h.xyz[2] == 1 and h.xyz[0]+math.sqrt(2) < 1e-5:
        found = True
    if not found:
      return "Movers.Test() MoverNH3Rotator basic: bad H placement"

    # Check fitness function preferring 180 and +/- 120 from there rotations
    zero = mover._preferenceFunction(0)
    oneEighty = mover._preferenceFunction(180)
    off1 = mover._preferenceFunction(180+120)
    off2 = mover._preferenceFunction(180-120)
    if abs(off1 - oneEighty) > 1e-5:
      return "Movers.Test() MoverNH3Rotator basic: bad preference function"
    if abs(off2 - oneEighty) > 1e-5:
      return "Movers.Test() MoverNH3Rotator basic: bad preference function"
    if zero - oneEighty < 1e-5:
      return "Movers.Test() MoverNH3Rotator basic: bad preference function"

  except Exception as e:
    return "Movers.Test() MoverNH3Rotator basic: Exception during test: "+str(e)+"\n"+traceback.format_exc()
    
  # Test the MoverAromaticMethylRotator class.
  try:
    # Construct a MoverAromaticMethylRotator that has one hydrogen start out at 45 degrees around Z and the
    # other two at +/-120 degrees from that one.
    # They are bonded to a Carbon and partner that are vertical and then partner is bonded to two
    # friends that are in the Y=0 plane.  This should cause us to get the one of the hydrogens at
    # +90 or -90 and the others 120 away from the first with only two coarse choices and no fine choices.
    axis = flex.vec3_double([ [0,0,0], [0,0,1] ])
    h1 = pdb.hierarchy.atom()
    h1.element = "H"
    h1.xyz = [ 1.0, 1.0, 1.0 ]

    h2 = pdb.hierarchy.atom()
    h2.element = "H"
    h2.xyz = _rotateAroundAxis(h1, axis, -120)

    h3 = pdb.hierarchy.atom()
    h3.element = "H"
    h3.xyz = _rotateAroundAxis(h1, axis, 120)

    n = pdb.hierarchy.atom()
    n.element = "C"
    n.xyz = [ 0.0, 0.0, 0.0 ]

    p = pdb.hierarchy.atom()
    p.xyz = [ 0.0, 0.0,-1.0 ]

    f1 = pdb.hierarchy.atom()
    f1.xyz = [ 1.0, 0.0,-2.0 ]

    f2 = pdb.hierarchy.atom()
    f1.xyz = [-1.0, 0.0,-2.0 ]

    # Build the hierarchy so we can reset the i_seq values.
    ag = pdb.hierarchy.atom_group()
    ag.append_atom(h1)
    ag.append_atom(h2)
    ag.append_atom(h3)
    ag.append_atom(n)
    ag.append_atom(p)
    ag.append_atom(f1)
    ag.append_atom(f2)
    rg = pdb.hierarchy.residue_group()
    rg.append_atom_group(ag)
    c = pdb.hierarchy.chain()
    c.append_residue_group(rg)
    m = pdb.hierarchy.model()
    m.append_chain(c)
    m.atoms().reset_i_seq()

    bondedNeighborLists = {}
    bondedNeighborLists[h1] = [ n ]
    bondedNeighborLists[h2] = [ n ]
    bondedNeighborLists[h3] = [ n ]
    bondedNeighborLists[n] = [ h1, h2, h3, p ]
    bondedNeighborLists[p] = [ n, f1, f2 ]
    bondedNeighborLists[f1] = [ p ]
    bondedNeighborLists[f2] = [ p ]

    mover = MoverAromaticMethylRotator(n, bondedNeighborLists)

    # Check for a hydrogen on the +/-Y axis at a distance of sqrt(2) from the Z axis
    found = False
    for h in [h1, h2, h3]:
      if h.xyz[2] == 1 and abs(abs(h.xyz[1])-math.sqrt(2)) < 1e-5:
        found = True
    if not found:
      return "Movers.Test() MoverAromaticMethylRotator basic: bad H placement"

    # Check that we get two coarse and no fine orientations
    coarse = mover.CoarsePositions().positions
    if len(coarse) != 2:
      return "Movers.Test() MoverAromaticMethylRotator basic: bad coarse count: "+str(len(coarse))
    fine = mover.FinePositions(0).positions
    if len(fine) != 0:
      return "Movers.Test() MoverAromaticMethylRotator basic: bad fine count: "+str(len(fine))

  except Exception as e:
    return "Movers.Test() MoverAromaticMethylRotator basic: Exception during test: "+str(e)+"\n"+traceback.format_exc()
    
  # Test the MoverTetrahedralMethylRotator class.
  try:
    # Construct a MoverTetrahedralMethylRotator that has one hydrogen start out at 45 degrees around Z and the
    # other two at +/-120 degrees from that one.
    # They are bonded to a Carbon and partner that are vertical and then partner is bonded to three
    # friends with one in the +X direction.  This should cause us to get the one of the hydrogens at
    # 180 the others 120 away from the first.
    axis = flex.vec3_double([ [0,0,0], [0,0,1] ])
    h1 = pdb.hierarchy.atom()
    h1.element = "H"
    h1.xyz = [ 1.0, 1.0, 1.0 ]

    h2 = pdb.hierarchy.atom()
    h2.element = "H"
    h2.xyz = _rotateAroundAxis(h1, axis, -120)

    h3 = pdb.hierarchy.atom()
    h3.element = "H"
    h3.xyz = _rotateAroundAxis(h1, axis, 120)

    n = pdb.hierarchy.atom()
    n.element = "C"
    n.xyz = [ 0.0, 0.0, 0.0 ]

    p = pdb.hierarchy.atom()
    p.xyz = [ 0.0, 0.0,-1.0 ]

    f1 = pdb.hierarchy.atom()
    f1.xyz = [ 1.0, 0.0,-2.0 ]

    f2 = pdb.hierarchy.atom()
    f2.xyz = _rotateAroundAxis(f1, axis, -120)

    f3 = pdb.hierarchy.atom()
    f3.xyz = _rotateAroundAxis(f1, axis,  120)

    # Build the hierarchy so we can reset the i_seq values.
    ag = pdb.hierarchy.atom_group()
    ag.append_atom(h1)
    ag.append_atom(h2)
    ag.append_atom(h3)
    ag.append_atom(n)
    ag.append_atom(p)
    ag.append_atom(f1)
    ag.append_atom(f2)
    ag.append_atom(f3)
    rg = pdb.hierarchy.residue_group()
    rg.append_atom_group(ag)
    c = pdb.hierarchy.chain()
    c.append_residue_group(rg)
    m = pdb.hierarchy.model()
    m.append_chain(c)
    m.atoms().reset_i_seq()

    bondedNeighborLists = {}
    bondedNeighborLists[h1] = [ n ]
    bondedNeighborLists[h2] = [ n ]
    bondedNeighborLists[h3] = [ n ]
    bondedNeighborLists[n] = [ h1, h2, h3, p ]
    bondedNeighborLists[p] = [ n, f1, f2, f3 ]
    bondedNeighborLists[f1] = [ p ]
    bondedNeighborLists[f2] = [ p ]
    bondedNeighborLists[f3] = [ p ]

    mover = MoverTetrahedralMethylRotator(n, bondedNeighborLists)

    # Check for a hydrogen on the +/-Y axis at a distance of sqrt(2) from the Z axis
    found = False
    for h in [h1, h2, h3]:
      if h.xyz[2] == 1 and h.xyz[0]+math.sqrt(2) < 1e-5:
        found = True
    if not found:
      return "Movers.Test() MoverTetrahedralMethylRotator basic: bad H placement"

    # Check fitness function preferring 180 and +/- 120 from there rotations.
    zero = mover._preferenceFunction(0)
    oneEighty = mover._preferenceFunction(180)
    off1 = mover._preferenceFunction(180+120)
    off2 = mover._preferenceFunction(180-120)
    if abs(off1 - oneEighty) > 1e-5:
      return "Movers.Test() MoverTetrahedralMethylRotator: bad preference function"
    if abs(off2 - oneEighty) > 1e-5:
      return "Movers.Test() MoverTetrahedralMethylRotator: bad preference function"
    if zero - oneEighty < 1e-5:
      return "Movers.Test() MoverTetrahedralMethylRotator: bad preference function"

  except Exception as e:
    return "Movers.Test() MoverTetrahedralMethylRotator basic: Exception during test: "+str(e)+"\n"+traceback.format_exc()

  # Test the MoverNH2Flip class.
  try:
    # @todo Test behavior with offsets for each atom so that we test the generic case.
    # Construct a MoverNH2Flip that has the N, H's and Oxygen located (non-physically)
    # slightly in the +Y direction out of the X-Z plane, with the Hydrogens 120 around the
    # same offset axis.
    # They are bonded to a Carbon and friend that are on the Z axis.
    # Non-physically, atoms are 1 unit apart.
    p = pdb.hierarchy.atom()
    p.xyz = [ 0.0, 0.0, 0.0 ]

    f = pdb.hierarchy.atom()
    f.element = "C"
    f.xyz = [ 0.0, 0.0,-1.0 ]

    # Nitrogen and Oxygen are +/-120 degrees from carbon-carbon bond
    axis = flex.vec3_double([ [0,0,0], [0,1,0] ])
    n = pdb.hierarchy.atom()
    n.element = "N"
    n.xyz = _rotateAroundAxis(f, axis,-120) + _lvec3([0,0.01,0])

    o = pdb.hierarchy.atom()
    o.element = "O"
    o.xyz = _rotateAroundAxis(f, axis, 120) + _lvec3([0,0.01,0])

    # Hydrogens are +/-120 degrees from nitrogen-carbon bond
    axis = flex.vec3_double([ n.xyz, [0,1,0] ])
    h1 = pdb.hierarchy.atom()
    h1.element = "H"
    h1.xyz = _rotateAroundAxis(p, axis,-120) + _lvec3([0,0.01,0])

    h2 = pdb.hierarchy.atom()
    h2.element = "H"
    h2.xyz = _rotateAroundAxis(p, axis, 120) + _lvec3([0,0.01,0])

    # Build the hierarchy so we can reset the i_seq values.
    ag = pdb.hierarchy.atom_group()
    ag.append_atom(h1)
    ag.append_atom(h2)
    ag.append_atom(n)
    ag.append_atom(o)
    ag.append_atom(p)
    ag.append_atom(f)
    rg = pdb.hierarchy.residue_group()
    rg.append_atom_group(ag)
    c = pdb.hierarchy.chain()
    c.append_residue_group(rg)
    m = pdb.hierarchy.model()
    m.append_chain(c)
    m.atoms().reset_i_seq()

    bondedNeighborLists = {}
    bondedNeighborLists[h1] = [ n ]
    bondedNeighborLists[h2] = [ n ]
    bondedNeighborLists[n] = [ h1, h2, p ]
    bondedNeighborLists[o] = [ p ]
    bondedNeighborLists[p] = [ n, o, f ]
    bondedNeighborLists[f] = [ p ]

    mover = MoverNH2Flip(n, bondedNeighborLists)
    fixed = mover.FixUp(1).newPositions

    # Ensure that the results meet the specifications:
    # 1) New Oxygen on the line from the alpha carbon to the old Nitrogen
    # 2) New plane of Oxygen, Nitrogen, Alpha Carbon matches old plane, but flipped
    # 3) Carbon has moved slightly due to rigid-body motion

    # @todo


  except Exception as e:
    return "Movers.Test() MoverNH2Flip basic: Exception during test: "+str(e)+"\n"+traceback.format_exc()

  # @todo Test other Mover subclasses

  return ""

##################################################################################
# Internal helper functions to make things that are compatible with vec3_double so
# that we can do math on them.  We need a left-hand and right-hand one so that
# we can make both versions for multiplication.
def _rvec3 (xyz) :
  return scitbx.matrix.rec(xyz, (3,1))
def _lvec3 (xyz) :
  return scitbx.matrix.rec(xyz, (1,3))

##################################################################################
# Internal helper functions for angle manipulation.
def _rotateOppositeFriend(atom, axis, partner, friends):
  '''Rotate the atom to point away from one of the friends.  This means placing it
     within the plane perpendicular to the axis of rotation through the point on that axis
     that it is closest to at the same distance it starts out from that axis and in a
     direction that is the negation of the vector from the partner to the friend projected
     into the plane perpendicular to the axis and then normalized.
     :param atom: iotbx.pdb.hierarchy.atom to be moved.
     :param partner: iotbx.pdb.hierarchy.atom atom that is bonded to the neighbor of
     the atom.
     :param friends: flex iotbx.pdb.hierarchy.atom list of atoms bonded to the partner
     besides the neighbor.
     :param axis: flex array with two scitbx::vec3<double> points, the first
     of which is the origin and the second is a vector pointing in the direction
     of the axis of rotation.  Positive rotations will be right-handed rotations
     around this axis.
     :returns the new location for the atom.
  '''
  normal = _rvec3(axis[1])
  friend = friends[0]
  friendFromPartner = _lvec3(friend.xyz) - _lvec3(partner.xyz)
  alongAxisComponent = (friendFromPartner * normal)
  friendFromPartner = _rvec3(friend.xyz) - _rvec3(partner.xyz)
  inPlane = friendFromPartner - normal*alongAxisComponent
  normalizedOffset = -inPlane.normalize()

  d = -_lvec3(atom.xyz)*normal
  t = - (d + (_lvec3(axis[0])) * normal)
  nearPoint = _rvec3(axis[0]) + normal*t
  distFromNearPoint = (_rvec3(atom.xyz)-nearPoint).length()

  return nearPoint + distFromNearPoint * normalizedOffset

def _rotateAroundAxis(atom, axis, degrees):
  '''Rotate the atom about the specified axis by the specified number of degrees.
     :param atom: iotbx.pdb.hierarchy.atom or scitbx::vec3<double> or
     scitbx.matrix.rec(xyz, (3,1)) to be moved.
     :param axis: flex array with two scitbx::vec3<double> points, the first
     of which is the origin and the second is a vector pointing in the direction
     of the axis of rotation.  Positive rotations will be right-handed rotations
     around this axis.
     :param degrees: How much to rotate the atom around the axis.
     Positive rotation is right-handed around the axis.
     :returns the new location for the atom.
  '''
  # If we have an atom, get its position.  Otherwise, we have a position passed
  # in.
  try:
    pos = atom.xyz
  except:
    pos = _rvec3(atom)

  # Project the atom position onto the axis, finding its closest point on the axis.
  # The position lies on a plane whose normal points along the axis vector.  The
  # point we seek is the intersection of the axis with this plane.
  # The plane equation will be the normalized axis direction vector and the offset
  # from the origin such that N.point + d = 0 defines the plane.
  # Solve for the time at which the line's ray crosses the plane and then solve for
  # the location along the line at that time.  t = - (d + (lineOrigin * planeNormal)) /
  # (lineDirection * planeNormal).  Because the line direction and normal are the
  # same, the divisor is 1.
  normal = _lvec3(axis[1]).normalize()
  d = -normal*pos
  t = - (d + (normal * _rvec3(axis[0])))
  nearPoint = _lvec3(axis[0]) + t * normal

  # Find the vector from the closest point towards the atom, which is its offset
  offset = _lvec3(pos) - nearPoint

  # Rotate the offset vector around the axis by the specified angle.  Add the new
  # offset to the closest point. Store this as the new location for this atom and angle.
  newOffset = offset.rotate_around_origin(_lvec3(axis[1]), degrees*math.pi/180)
  return nearPoint + newOffset

 # If we're run on the command line, test our classes and functions.
if __name__ == '__main__':

  ret = Test()
  if len(ret) == 0:
    print('Success!')
  else:
    print(ret)

  assert (len(ret) == 0)
