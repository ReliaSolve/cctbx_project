from __future__ import division
import traceback
import sys, os
op = os.path

def report_fraction_of_negative_observations_if_any(id_code, obs):
  d = obs.data()
  n_neg = (d < 0).count(True)
  n_all = d.size()
  if (n_neg != 0 and n_all != 0):
    print obs.info()
    print "fraction_of_negative_obs: %.6g (%d of %d)" % (
      n_neg / n_all, n_neg, n_all)
    neg = d.select(d < 0)
    pos = d.select(d >= 0)
    from cctbx.array_family import flex
    def hist(data):
      from cStringIO import StringIO
      sio = StringIO()
      flex.histogram(data=data, n_slots=10) \
        .show(f=sio, prefix="  ", format_cutoffs="%8.2f")
      return sio.getvalue().splitlines()
    lines_neg = hist(-neg)
    lines_pos = hist(pos)
    pair_fmt = "%-35s | %s"
    print pair_fmt % (
      "Histogram of negative observations:",
        "positive observations:")
    for pair in zip(lines_neg, lines_pos):
      print pair_fmt % pair

class cod_data(object):

  __slots__ = [
    "cod_id",
    "c_obs",
    "xray_structure",
    "non_hydrogen_selection",
    "edge_list"]

  def __init__(O, cod_id, hkl_cif_pair):
    O.cod_id = cod_id
    O.c_obs = None
    O.xray_structure = None
    O.non_hydrogen_selection = None
    O.edge_list = None
    refl_file, model_file = hkl_cif_pair
    import iotbx.cif.builders
    print "refl_file:", refl_file
    print "model_file:", model_file
    refl_cif = iotbx.cif.reader(file_path=refl_file)
    model_cif = iotbx.cif.reader(file_path=model_file)
    for cif_obj in [model_cif, refl_cif]:
      for cif_block in cif_obj.model().values():
        value = cif_block.get("_cod_error_flag")
        if (value in ["errors", "retracted"]):
          print "SKIPPING: _cod_error_flag %s: %s" % (value, cod_id)
          return
        keys = set(cif_block.keys())
        if (len(set([
              "_space_group_symop_ssg_operation_algebraic",
              "_space_group_ssg_name"]).intersection(keys)) != 0):
          print "SKIPPING: COD entry with super-space group:", cod_id
          return
        if (len(set([
              "_refln_index_m",
              "_refln_index_m_1"]).intersection(keys)) != 0):
          print "SKIPPING: COD entry with _refln_index_m:", cod_id
          return
        for key in keys:
          if (key.startswith("_pd_")):
            print "SKIPPING: COD entry with powder data:", cod_id
            return
    from_coordinate_files = []
    from_reflection_files = []
    def get_cs(cif, buffer):
      for cif_block in cif.model().values():
        cs = iotbx.cif.builders.crystal_symmetry_builder(
          cif_block=cif_block).crystal_symmetry
        buffer.append(cs)
    get_cs(refl_cif, from_reflection_files)
    get_cs(model_cif, from_coordinate_files)
    import cctbx.crystal
    combined_cs = cctbx.crystal.select_crystal_symmetry(
      from_coordinate_files=from_coordinate_files,
      from_reflection_files=from_reflection_files)
    if (combined_cs.unit_cell() is None):
      raise RuntimeError("Unit cell not found in both cif and hkl files.")
    if (combined_cs.space_group_info() is None):
      raise RuntimeError("Space group not found in both cif and hkl file.")
    #
    miller_arrays = refl_cif.as_miller_arrays()
    meas_a = []
    meas_i = []
    for ma in miller_arrays:
      s = str(ma.info())
      if (s.find("_meas") >= 0):
        if (ma.is_xray_intensity_array()):
          meas_i.append(ma)
        elif (ma.is_xray_amplitude_array()):
          meas_a.append(ma)
        else:
          continue
        report_fraction_of_negative_observations_if_any(cod_id, ma)
    if (len(meas_i) != 0):
      O.c_obs = meas_i[0]
    elif (len(meas_a) != 0):
      O.c_obs = meas_a[0]
    else:
      raise RuntimeError("Missing diffraction data.")
    O.c_obs = O.c_obs.customized_copy(
      crystal_symmetry=combined_cs)
    print "."*79
    O.c_obs.show_comprehensive_summary()
    print "."*79
    #
    O.xray_structure = cctbx.xray.structure.from_cif(
      file_path=model_file, data_block_name=cod_id)
    O.xray_structure = O.xray_structure.customized_copy(
      crystal_symmetry=combined_cs)
    O.xray_structure.show_summary().show_scatterers()
    print "."*79
    #
    O.non_hydrogen_selection = (~O.xray_structure.hd_selection()).iselection()
    #
    O.edge_list = O.process_geom_bond(model_cif)
    if (O.edge_list is not None):
      print "len(edge_list):", len(O.edge_list), cod_id

  def have_zero_occupancies(O):
    return not O.xray_structure.scatterers().extract_occupancies().all_ne(0)

  def have_shelxl_compatible_scattering_types(O):
    from cctbx.eltbx.xray_scattering import \
      shelxl_97_2_980324_tabulated_chemical_elements as known
    for sc in O.xray_structure.scatterers():
      if (sc.scattering_type.strip().upper() not in known):
        return False
    return True

  def have_close_contacts(O, min_distance):
    if (min_distance <= 0):
      return False
    xs = O.xray_structure.select(selection=O.non_hydrogen_selection)
    pat = xs.pair_asu_table(distance_cutoff=min_distance)
    pst = pat.extract_pair_sym_table()
    from cctbx import crystal
    from cctbx.array_family import flex
    dists = crystal.get_distances(
      pair_sym_table=pst,
      orthogonalization_matrix=xs.unit_cell().orthogonalization_matrix(),
      sites_frac=xs.sites_frac())
    print "Close contacts:", dists.size()
    if (dists.size() != 0):
      pat.show_distances(sites_frac=xs.sites_frac())
      return True
    return False

  def have_sys_absent(O):
    return (O.c_obs.sys_absent_flags().data().count(True) != 0)

  def have_redundant_data(O):
    return not O.c_obs.is_unique_set_under_symmetry()

  def have_bad_sigmas(O):
    if (O.c_obs.sigmas() is None):
      print "Missing sigmas:", O.cod_id
      return True
    sel = (O.c_obs.data() == 0) & (O.c_obs.sigmas() == 0)
    result = not O.c_obs.select(~sel).sigmas().all_gt(0)
    if (result):
      print "Zero or negative sigmas:", O.cod_id
    return result

  def f_obs_and_f_calc_agree_well(O, co):
    if (O.c_obs.indices().size() == 0): return False
    from cctbx.array_family import flex
    f_obs = O.c_obs.as_amplitude_array(algorithm="xtal_3_7")
    f_calc = f_obs.structure_factors_from_scatterers(
      xray_structure=O.xray_structure).f_calc().amplitudes()
    fan_out_sel = f_obs.f_obs_f_calc_fan_outlier_selection(
      f_calc=f_calc,
      offset_low=co.fan_offset_low,
      offset_high=co.fan_offset_high,
      also_return_x_and_y=True)
    if (fan_out_sel is None):
      return False
    if (co.i_obs_i_calc_plot and f_obs.indices().size() != 0):
      from libtbx import pyplot
      xs = O.c_obs.as_intensity_array(algorithm="simple").data()
      ys = flex.pow2(f_calc.data())
      pyplot.plot(xs.as_numpy_array(), ys.as_numpy_array(), "ro")
      pyplot.show()
    fan_out_sel, x, y = fan_out_sel
    fan_in_sel = ~fan_out_sel
    if (co.f_obs_f_calc_plot):
      from libtbx import pyplot
      xs = x.select(fan_out_sel)
      ys = y.select(fan_out_sel)
      if (xs.size() == 0):
        pyplot.plot(x.as_numpy_array(), y.as_numpy_array(), "bo")
      else:
        pyplot.plot(xs.as_numpy_array(), ys.as_numpy_array(), "ro")
        xs = x.select(fan_in_sel)
        ys = y.select(fan_in_sel)
        if (xs.size() != 0):
          pyplot.plot(xs.as_numpy_array(), ys.as_numpy_array(), "bo")
      pyplot.plot_pairs(
        [(co.fan_offset_low,0), (1,1-co.fan_offset_high)], "r-")
      pyplot.plot_pairs(
        [(0,co.fan_offset_low), (1-co.fan_offset_high,1)], "r-")
      pyplot.plot_pairs([(0,0), (1,1)], "k--")
      pyplot.show()
    fan_outlier_fraction = fan_out_sel.count(True) / fan_out_sel.size()
    def cc_r1(fo, fc):
      lc = flex.linear_correlation(fo.data(), fc.data())
      assert lc.is_well_defined()
      cc = lc.coefficient()
      from libtbx import Auto
      r1 = f_obs.r1_factor(other=f_calc, scale_factor=Auto)
      return cc, r1
    cc_all, r1_all = cc_r1(f_obs, f_calc)
    cc_in, r1_in = cc_r1(f_obs.select(fan_in_sel), f_calc.select(fan_in_sel))
    print "f_obs_f_calc %s" % O.cod_id, \
      "| cc_all %.4f | r1_all %.4f | out %.4f | cc_in %.4f | r1_in %.4f |" % (
        cc_all, r1_all, fan_outlier_fraction, cc_in, r1_in)
    if (fan_outlier_fraction > co.max_fan_outlier_fraction):
      return False
    if (cc_all < co.min_f_obs_f_calc_correlation):
      return False
    return True

  def is_useful(O, co):
    if (O.c_obs is None): return False
    if (O.non_hydrogen_selection.size() > co.max_atoms): return False
    if (O.have_zero_occupancies()): return False
    if (O.have_close_contacts(co.min_distance)): return False
    if (not O.have_shelxl_compatible_scattering_types()): return False
    if (O.have_sys_absent()): return False
    if (O.have_redundant_data()): return False
    if (O.have_bad_sigmas()): return False
    if (not O.f_obs_and_f_calc_agree_well(co)): return False
    if (    co.at_least_one_special_position
        and O.xray_structure.special_position_indices().size() == 0):
      return False
    return True

  def process_geom_bond(O, model_cif):
    xs = O.xray_structure
    scs = xs.scatterers()
    i_seq_by_lbl = dict(zip(scs.extract_labels(), range(scs.size())))
    if (len(i_seq_by_lbl) != scs.size()):
      return None
    edge_set = set()
    for cif_block in model_cif.model().values():
      lbl_lists = [cif_block.get("_geom_bond_atom_site_label_"+s)
        for s in "12"]
      if (lbl_lists.count(None) != 0):
        return None
      if (len(lbl_lists[0]) != len(lbl_lists[1])):
        return None
      for lbl_pair in zip(*lbl_lists):
        i_seqs = tuple(sorted([i_seq_by_lbl.get(lbl) for lbl in lbl_pair]))
        if (i_seqs.count(None) != 0):
          return None
        if (i_seqs in edge_set):
          return None
        edge_set.add(i_seqs)
    return sorted(edge_set)

  def quick_info(O):
    return (
      O.non_hydrogen_selection.size(),
      O.c_obs.space_group().order_p(),
      O.c_obs.indices().size(),
      O.c_obs.d_min())

def build_hkl_cif(cod_ids):
  envar = "COD_SVN_WORKING_COPY"
  cod_svn = os.environ.get(envar)
  if (cod_svn is None):
    msg = [
      "Environment variable %s not defined:" % envar,
      "  Usage:",
      "    mkdir /some/path",
      "    cd /some/path",
      "    svn checkout svn://www.crystallography.net/cod",
      "    export %s=/some/path/cod" % envar]
    raise RuntimeError("\n".join(msg))
  cif_dir = op.join(cod_svn, "cif")
  hkl_dir = op.join(cod_svn, "hkl")
  hkl_cif = []
  if (len(cod_ids) == 0):
    hkl_only = []
    for sub_dir in sorted(os.listdir(hkl_dir)):
      if (sub_dir.startswith(".")): continue
      hkl_sub_dir = op.join(hkl_dir, sub_dir)
      for node in sorted(os.listdir(hkl_sub_dir)):
        if (node.startswith(".")): continue
        if (not node.endswith(".hkl")): continue
        cod_id = node[:-4]
        hkl_path = op.join(hkl_sub_dir, node)
        cif_path = op.join(cif_dir, sub_dir, cod_id+".cif")
        if (not op.isfile(cif_path)):
          hkl_only.append(hkl_path)
        else:
          hkl_cif.append((hkl_path, cif_path))
    print "Number of hkl without cif:", len(hkl_only)
  else:
    n_missing_all = 0
    for cod_id in cod_ids:
      hkl_path = op.join(hkl_dir, cod_id[0], cod_id+".hkl")
      cif_path = op.join(cif_dir, cod_id[0], cod_id+".cif")
      n_missing = 0
      if (not op.isfile(cif_path)):
        print "Missing COD cif file:", cif_path
        n_missing += 1
      if (not op.isfile(hkl_path)):
        print "Missing COD hkl file:", hkl_path
        n_missing += 1
      if (n_missing == 0):
        hkl_cif.append((hkl_path, cif_path))
      else:
        n_missing_all += n_missing
    if (n_missing_all != 0):
      raise RuntimeError("Number of missing COD files: %d" % n_missing_all)
  print "Number of hkl+cif:", len(hkl_cif)
  return hkl_cif

def run(args, command_name):
  from iotbx.option_parser import option_parser as iotbx_option_parser
  from libtbx import easy_pickle
  import libtbx.utils
  show_times = libtbx.utils.show_times(time_start="now")
  command_line = (iotbx_option_parser(
    usage=command_name+" [options] [cod_id...]")
    .enable_chunk(easy_all=True)
    .enable_multiprocessing()
    .option(None, "--max_atoms",
      type="int",
      default=99,
      metavar="INT")
    .option(None, "--min_distance",
      type="float",
      default=0.5,
      metavar="FLOAT")
    .option(None, "--i_obs_i_calc_plot",
      action="store_true",
      default=False)
    .option(None, "--f_obs_f_calc_plot",
      action="store_true",
      default=False)
    .option(None, "--max_fan_outlier_fraction",
      type="float",
      default=0.05,
      metavar="FLOAT")
    .option(None, "--fan_offset_low",
      type="float",
      default=0.05,
      metavar="FLOAT")
    .option(None, "--fan_offset_high",
      type="float",
      default=0.10,
      metavar="FLOAT")
    .option(None, "--min_f_obs_f_calc_correlation",
      type="float",
      default=0.99,
      metavar="FLOAT")
    .option(None, "--at_least_one_special_position",
      action="store_true",
      default=False)
    .option(None, "--pickle_dir",
      type="str",
      default="cod_ma_xs",
      metavar="PATH")
  ).process(args=args)
  if (command_line.run_multiprocessing_chunks_if_applicable(
        command_call=[command_name])):
    show_times()
    return
  co = command_line.options
  #
  hkl_cif = build_hkl_cif(cod_ids=command_line.args)
  #
  pickle_dir = co.pickle_dir
  if (co.at_least_one_special_position):
    pickle_dir += "_special"
  if (not op.isdir(pickle_dir)):
    from libtbx.path import makedirs_race
    makedirs_race(path=pickle_dir)
  n_caught = 0
  for i_pair,pair in enumerate(hkl_cif):
    cod_id = op.basename(pair[0])[:-4]
    if (i_pair % command_line.chunk.n != command_line.chunk.i): continue
    try:
      cd = cod_data(cod_id=cod_id, hkl_cif_pair=pair)
    except KeyboardInterrupt:
      print "CAUGHT EXCEPTION: KeyboardInterrupt"
      return
    except Exception, e:
      sys.stdout.flush()
      print >> sys.stderr, \
        "CAUGHT EXCEPTION: %s: %s: %s" % (command_name, cod_id, str(e))
      traceback.print_exc()
      print >> sys.stderr
      sys.stderr.flush()
      n_caught += 1
    else:
      if (cd.is_useful(co)):
        easy_pickle.dump(
          file_name="%s/%s.pickle" % (pickle_dir, cod_id),
          obj=(cd.c_obs, cd.xray_structure, cd.edge_list))
        print >> open("%s/qi_%s" % (pickle_dir, cod_id), "w"), \
          cd.quick_info()
      else:
        print "filtering out:", cod_id
      print "done_with:", cod_id
      print
  print
  print "Number of exceptions caught:", n_caught
  #
  show_times()
