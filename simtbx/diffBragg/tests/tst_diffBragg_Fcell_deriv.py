
from argparse import ArgumentParser
parser = ArgumentParser()
parser.add_argument("--plot", action='store_true')
parser.add_argument("--curvatures", action='store_true')
args = parser.parse_args()

if args.plot:
    import pylab as plt
    plt.figure()
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.stats import linregress


from scitbx.array_family import flex
from scitbx.matrix import sqr
from scitbx.matrix import rec
from simtbx.diffBragg.nanoBragg_crystal import nanoBragg_crystal
from cctbx import uctbx
from simtbx.diffBragg.sim_data import SimData
from dxtbx.model.crystal import Crystal
from IPython import embed


ucell = (70, 60, 50, 90.0, 110, 90.0)
symbol = "C121"

a_real, b_real, c_real = sqr(uctbx.unit_cell(ucell).orthogonalization_matrix()).transpose().as_list_of_lists()
C = Crystal(a_real, b_real, c_real, symbol)

# random raotation
rotation = Rotation.random(num=1, random_state=101)[0]
Q = rec(rotation.as_quat(), n=(4, 1))
rot_ang, rot_axis = Q.unit_quaternion_as_axis_and_angle()
C.rotate_around_origin(rot_axis, rot_ang)
a_rot, b_rot, c_rot = C.get_real_space_vectors()

# STEP4:
# make a nanoBragg crystal to pass to diffBragg
nbcryst = nanoBragg_crystal()
nbcryst.dxtbx_crystal = C
nbcryst.n_mos_domains = 1
nbcryst.thick_mm = 0.01
nbcryst.Ncells_abc = (7, 7, 7)

# STEP5: make an instance of diffBRagg, use the simData wrapper
SIM = SimData()
# overwrite the default detector with a smaller pixels one
SIM.detector = SimData.simple_detector(300, 0.1, (700, 700))
SIM.crystal = nbcryst
Fcell = 1e3
SIM.instantiate_diffBragg(oversample=0, verbose=0, default_F=Fcell)
# D is an instance of diffBragg with reasonable parameters
# and our dxtbx crystal created above
D = SIM.D
D.progress_meter = True

# STEP6:
# initialize the derivative managers for the unit cell parameters
fcell = 11
D.refine(fcell)
D.initialize_managers()

roi = ((0, 699), (0, 699))
rX = slice(roi[0][0], roi[0][1], 1)
rY = slice(roi[1][0], roi[1][1], 1)
D.region_of_interest = roi

# STEP7:
# compute the scattering and its derivative
print("Adding diffBragg spots")
# Set all miller indices to have the same Fcell value
indices, data = D.Fhkl_tuple
data = flex.double(np.ones(len(indices))*Fcell)
D.Fhkl_tuple = indices, data

D.add_diffBragg_spots()

print("Done!")
img = D.raw_pixels_roi.as_numpy_array()

# reset all pixel values
D.raw_pixels *= 0
D.raw_pixels_roi *= 0

first_deriv = D.get_derivative_pixels(fcell).as_numpy_array()
if args.curvatures:
    second_deriv = D.get_second_derivative_pixels(fcell).as_numpy_array()


# STEP8
# iterate over the parameters and do a finite difference test for each one
# parameter shifts:
diffs = []
diffs2 = []
error2 = []
all_error = []
shifts = [1e-5*(i**2) for i in range(1, 30)]
for i_shift, percent_shift in enumerate(shifts):

    # TODO compute param shift (different for each HKL)
    delta_F = Fcell * percent_shift*1e-2

    #param_shift = var[i_param] * percent_shift

    #var[i_param] += param_shift
    # TODO step Fcell forward
    D.Fhkl_tuple = indices, data+delta_F
    D.add_diffBragg_spots()
    img_forward = D.raw_pixels_roi.as_numpy_array()

    # reset for next computation
    D.raw_pixels_roi *= 0
    D.raw_pixels *= 0

    if args.curvatures:
        # estimate the second derivative
        #TODO step Fcell backward
        D.add_diffBragg_spots()
        img_backward = D.raw_pixels_roi.as_numpy_array()

        # reset for next computation
        D.raw_pixels_roi *= 0
        D.raw_pixels *= 0

    finite_deriv = (img_forward-img) / delta_F

    bragg = img > 10
    ave_error = np.abs(finite_deriv[bragg] - first_deriv[bragg]).mean()
    all_error.append(ave_error)
    print ("error=%f, step=%f" % (ave_error, delta_F))

    if args.curvatures:
        finite_second_deriv = (img_forward - 2*img + img_backward) / delta_F / delta_F
        if args.plot:
            plt.clf()
            plt.subplot(121)
            plt.imshow(finite_second_deriv)
            plt.title("finite second diff")
            plt.subplot(122)
            plt.imshow(second_deriv)
            plt.title("analytical")
            plt.draw()
            plt.suptitle("Shift=%2.7f ( %d / %d),\n error=%2.7g"
                         % (delta_F, i_shift + 1, len(shifts), ave_error))
            plt.pause(0.8)

if args.plot:
    plt.clf()
    plt.plot(shifts, all_error, 'o')
    plt.show()

l = linregress(shifts, all_error)
assert l.rvalue > .9999  # this is definitely a line!
assert l.slope > 0
assert l.pvalue < 1e-6

print("OK!")

