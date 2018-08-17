#ifndef CCTBX_ADP_RESTRAINTS_RIGU_H
#define CCTBX_ADP_RESTRAINTS_RIGU_H

#include <cctbx/import_scitbx_af.h>
#include <cctbx/error.h>
#include <cctbx/adptbx.h>
#include <cctbx/adp_restraints/adp_restraints.h>
#include <scitbx/matrix/matrix_vector_operations.h>
#include <iostream>

namespace cctbx { namespace adp_restraints {

using scitbx::vec3;
using scitbx::mat3;
using scitbx::sym_mat3;

  /** RIGU restraint
   * Restrains U33, U13 and U23 of 2 adps expressed in a cartesian base along the bond of the 2 atoms.
   * U33 is aligned along the bond
   * See Thorn, A., Dittrich, B. & Sheldrick, G. M. (2012). Acta Cryst. A68, 448-451.
   * and Parois, P., Arnold, J. & Cooper, R. (2018). J. Appl. Cryst. 51, 1059-1068.
  */

  struct rigu_proxy
  {
    //! Default constructor. Some data members are not initialized!
    rigu_proxy() {}

    //! Constructor.
    rigu_proxy(
      af::tiny<unsigned, 2> const& i_seqs_,
      double weight_)
    :
      i_seqs(i_seqs_),
      weight(weight_)
    {}

    //! Indices into array of sites.
    af::tiny<unsigned, 2> i_seqs;
    //! weight
    double weight;
  };

  class rigu {
  public:
    //! Constructor.
    rigu(
      af::tiny<scitbx::vec3<double>, 2> const& sites,
      af::tiny<scitbx::sym_mat3<double>, 2> const& u_cart,
      double weight_)
    :
      weight(weight_)
    {
      init_delta(sites, u_cart);
      calc_gradients();
    }

    //! Constructor.
    rigu(
      adp_restraint_params<double> const &params,
      rigu_proxy const& proxy)
    :
      weight(proxy.weight)
    {
      CCTBX_ASSERT(params.sites_cart.size() == params.u_cart.size());
      CCTBX_ASSERT(proxy.i_seqs[0] < params.sites_cart.size());
      CCTBX_ASSERT(proxy.i_seqs[1] < params.sites_cart.size());
      init_delta(
        af::tiny<scitbx::vec3<double>, 2>(
          params.sites_cart[proxy.i_seqs[0]], params.sites_cart[proxy.i_seqs[1]]),
        af::tiny<scitbx::sym_mat3<double>, 2>(
          params.u_cart[proxy.i_seqs[0]], params.u_cart[proxy.i_seqs[1]]));
      calc_gradients();
    }

    //! weight * delta[i]**2.
    double
    residual33() const { 
      return weight * scitbx::fn::pow2(delta_33_); 
    }
    double
    residual13() const { 
      return weight * scitbx::fn::pow2(delta_13_); 
    }
    double
    residual23() const { 
      return weight * scitbx::fn::pow2(delta_23_); 
    }
    double
    residual() const { 
      return residual33() + residual13() + residual23(); 
    }
    
    //! Gradient of U_cart after linear transformation RM (basis aligned along bond) in respect to Uij_cart
    scitbx::sym_mat3<double> grad_delta_n(int r) const {
      scitbx::sym_mat3<double> result;

      //! partial derivatives against Uij are then just a row in dRUcart 
      for(int i = 0; i< 6; i++) {
        result[i] = dRUcart[r][i];
      }
      return result;
    }

    //! Gradient of residual with respect to u_cart[0]
    scitbx::sym_mat3<double>
    gradient_33() const
    {
      scitbx::sym_mat3<double> result = grad_delta_n(8);
      result *= 2 * weight * delta_33_;
      return result;
    }
    scitbx::sym_mat3<double>
    gradient_13() const
    {
      scitbx::sym_mat3<double> result = grad_delta_n(6);
      result *= 2 * weight * delta_13_;
      return result;
    }
    scitbx::sym_mat3<double>
    gradient_23() const
    {
      scitbx::sym_mat3<double> result = grad_delta_n(7);
      result *= 2 * weight * delta_23_;
      return result;
    }

    af::tiny<scitbx::sym_mat3<double>, 2>
    gradients33() const
    {
      af::tiny<scitbx::sym_mat3<double>, 2> result;
      result[0] = gradient_33();
      result[1] = -result[0];
      return result;
    }

    af::tiny<scitbx::sym_mat3<double>, 2>
    gradients13() const
    {
      af::tiny<scitbx::sym_mat3<double>, 2> result;
      result[0] = gradient_13();
      result[1] = -result[0];
      return result;
    }

    af::tiny<scitbx::sym_mat3<double>, 2>
    gradients23() const
    {
      af::tiny<scitbx::sym_mat3<double>, 2> result;
      result[0] = gradient_23();
      result[1] = -result[0];
      return result;
    }

    //! Support for rigu_residual_sum.
    /*! Not available in Python.
     */
    void
    add_gradients(
      af::ref<scitbx::sym_mat3<double> > const& gradients_aniso_cart,
      af::tiny<unsigned, 2> const& i_seqs) const
    {
      scitbx::sym_mat3<double> g0;
      g0 = gradient_33();
      gradients_aniso_cart[i_seqs[0]] += g0;
      gradients_aniso_cart[i_seqs[1]] += -g0;
      g0 = gradient_13();
      gradients_aniso_cart[i_seqs[0]] += g0;
      gradients_aniso_cart[i_seqs[1]] += -g0;
      g0 = gradient_23();
      gradients_aniso_cart[i_seqs[0]] += g0;
      gradients_aniso_cart[i_seqs[1]] += -g0;
    }

    void
    linearise(
      uctbx::unit_cell const &unit_cell,
      cctbx::restraints::linearised_eqns_of_restraint<double> &linearised_eqns,
      cctbx::xray::parameter_map<cctbx::xray::scatterer<double> > const &parameter_map,
      af::tiny<unsigned, 2> const& i_seqs) const
    {
      af::const_ref<double, af::mat_grid> const &f
        = unit_cell.u_star_to_u_cart_linear_map();
      scitbx::sym_mat3<double> grad_u_cart;
      scitbx::sym_mat3<double> grad_u_star;
      std::size_t row_i;
      int const indices[3] = {8,6,7}; //! derivatives to consider: U33, U13, U23
      double const deltas[3] = {delta_33_,delta_13_,delta_23_};
      
      for (std::size_t k; k<3; k++) {
        grad_u_cart = grad_delta_n(indices[k]);
        scitbx::matrix::matrix_transposed_vector(
          6, 6, f.begin(), grad_u_cart.begin(), grad_u_star.begin());
        row_i = linearised_eqns.next_row();
        for (std::size_t i=0;i<2;i++) {
          if (i == 1) grad_u_star = -grad_u_star;
          cctbx::xray::parameter_indices const &ids_i
            = parameter_map[i_seqs[i]];
          if (ids_i.u_aniso == -1) continue;
          for (std::size_t j=0;j<6;j++) {
            linearised_eqns.design_matrix(row_i, ids_i.u_aniso+j)
              = grad_u_star[j];
          }
          linearised_eqns.weights[row_i] = weight;
          linearised_eqns.deltas[row_i] = deltas[k];
        }
      }
            
    }

    double delta_33() { return delta_33_; } 
    double delta_13() { return delta_13_; }
    double delta_23() { return delta_23_; }
    double delta() { return delta_33_+delta_13_+delta_23_; }

    double weight;

  protected:
    void init_delta(af::tiny<scitbx::vec3<double>, 2> const &sites,
      af::tiny<scitbx::sym_mat3<double>, 2> const &u_cart)
    {      
      
      //! first step, calculating the rotation matrix to align U33 along the bond
      vec3<double> rot3 = sites[0] - sites[1];
      
      // Any perpendicular axis will do
      vec3<double> rot2;
      rot2[0] = rot3[2];
      rot2[1] = rot3[2];
      rot2[2] = -rot3[0]-rot3[1];
    
      if(abs(rot2[0])+abs(rot2[1])+abs(rot2[1])<1e-4) {
        rot2[0] = -rot3[1]-rot3[2];
        rot2[1] = rot3[1];
        rot2[2] = rot3[1];
      }
    
      // Last axis to form a direct orthonormal basis
      vec3<double> rot1 = rot2.cross(rot3);

      RM.set_row(0, rot1.normalize());
      RM.set_row(1, rot2.normalize());
      RM.set_row(2, rot3.normalize());
    
      //! Calculating Ucart in the new basis 
      mat3<double> tmp1(u_cart[0]);
      RUcart1 = (RM*tmp1)*RM.transpose();
      mat3<double> tmp2(u_cart[1]);
      RUcart2 = (RM*tmp2)*RM.transpose();
    
      //! calculating the 3 deltas involved
      delta_33_ = RUcart1(2,2) - RUcart2(2,2);
      delta_13_ = RUcart1(0,2) - RUcart2(0,2);
      delta_23_ = RUcart1(1,2) - RUcart2(1,2);
    }

    //! Calculate all the partial derivatives of the adp in the local cartesian coordinate system.
    void calc_gradients() {
      /* See Parois, P., Arnold, J. & Cooper, R. (2018). J. Appl. Cryst. 51, 1059-1068.
       * for the detail on how it works
       *
       * The U tensors are vectorized as 9 elements vectors column by column to simplify the calculations
       * Operations like V = A U B translate then to vec(V) = (B^t @ A) U with @ the kronecker product
       */
      
      /** dUcart contains the 6 partial derivatives dU_cart/dUij_cart writen as vectors. 
       *  The 6 columns vectors are then stacked column wise to form dUcart
       */
      static const double dUcart[9][6] = {
        //dU11 dU22 dU33 dU12 dU13 dU23
        { 1,   0,   0,   0,   0,   0}, // U11
        { 0,   0,   0,   1,   0,   0}, // U21
        { 0,   0,   0,   0,   1,   0}, // U23
        { 0,   0,   0,   1,   0,   0}, // U21
        { 0,   1,   0,   0,   0,   0}, // U22
        { 0,   0,   0,   0,   0,   1}, // U23
        { 0,   0,   0,   0,   1,   0}, // U31
        { 0,   0,   0,   0,   0,   1}, // U32
        { 0,   0,   1,   0,   0,   0}, // U33
      };
      
      double kron[9][9];    
      int i,j,k,l,startRow,startCol;

      //! calulating the kronecker product    
      for(i=0;i<3;i++){
        for(j=0;j<3;j++){
          startRow = i*3;
          startCol = j*3;
          for(k=0;k<3;k++){
            for(l=0;l<3;l++){
              kron[startRow+k][startCol+l] = RM(i,j)*RM(k,l);
            }
          }
        }
      }
        
      //! vec(dRUcart) = kron vec(dUcart). Derivatives of (RUcart = RM Ucart RM^t)
      for (i = 0; i < 9; i++) {
        for (j = 0; j < 6; j++) {
          for (k = 0; k < 9; k++) {
            dRUcart[i][j] += kron[i][k] * dUcart[k][j];
          }
        }
      }       
    }
    
    double delta_33_;
    double delta_13_;
    double delta_23_;
    mat3<double> RUcart1, RUcart2;
    mat3<double> RM;
        
    double dRUcart[9][6];
  };

}} // namespace cctbx::adp_restraints

#endif // CCTBX_ADP_RESTRAINTS_RIGU_H
