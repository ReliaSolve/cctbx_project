// $Id$
/* Copyright (c) 2001 The Regents of the University of California through
   E.O. Lawrence Berkeley National Laboratory, subject to approval by the
   U.S. Department of Energy. See files COPYRIGHT.txt and
   cctbx/LICENSE.txt for further details.

   Revision history:
     2001 Oct 27: Redesign: AsymIndex (rwgk)
     2001 Jul 02: Merged from CVS branch sgtbx_special_pos (rwgk)
     2001 May 31: merged from CVS branch sgtbx_type (R.W. Grosse-Kunstleve)
     Apr 2001: SourceForge release (R.W. Grosse-Kunstleve)
 */

#ifndef CCTBX_SGTBX_MILLER_H
#define CCTBX_SGTBX_MILLER_H

#include <complex>
#include <cctbx/miller.h>

namespace cctbx {
  namespace Miller {

    //! Class for symmetrically equivalent Miller indices.
    class SymEquivIndex {
      public:
        //! Default constructor. Some data members are not initialized!
        SymEquivIndex() {}
        //! Constructor.
        /*! HR is the product of the input index H and the
            rotation part of a symmetry operation.
            <p>
            HT is the product of the input index H and the
            translation part of the symmetry operation,
            multiplied by the translation base-factor TBF
            in order to obtain an integer value for HT.
            <p>
            FriedelFlag indicates if Friedel's law was applied
            to arrive at H().
         */
        SymEquivIndex(const Index& HR, int HT, int TBF, bool FriedelFlag)
          : m_HR(HR), m_HT(HT) , m_TBF(TBF), m_FriedelFlag(FriedelFlag) {}
        //! The symmetrically equivalent index.
        Index H() const
        {
          if (m_FriedelFlag) return -m_HR;
          return m_HR;
        }
        //! Product of Miller index and rotation part of symmetry operation.
        const Index& HR() const { return m_HR; }
        //! Product of Miller index and translation part of symmetry operation.
        int HT() const { return m_HT; }
        //! Translation base factor.
        /*! This is the factor by which HT() is multiplied.
         */
        int TBF() const { return m_TBF; }
        //! Flag for application of Friedel's law.
        /*! For centric reflections, FriedelFlag() is always false.
         */
        bool FriedelFlag() const { return m_FriedelFlag; }

        //! Returns new SymEquivIndex with flipped FriedelFlag() if iMate != 0.
        SymEquivIndex Mate(int iMate = 1) const
        {
          if (iMate) return SymEquivIndex(m_HR, m_HT, m_TBF, !m_FriedelFlag);
          return *this;
        }

        /*! \brief Phase for equivalent index, given phase for
            input Miller index.
         */
        /*! Formula used:<br>
            deg == 0: phi_eq = phi_in - (2 * pi * HT()) / TBF();<br>
            deg != 0: phi_eq = phi_in - (360 * HT()) / TBF();<br>
            if (FriedelFlag()) phi_eq = -phi_eq;
         */
        template <class FloatType>
        FloatType phase_eq(const FloatType& phi_in, bool deg = false) const
        {
          FloatType period = cctbx::constants::two_pi;
          if (deg) period = 360;
          FloatType phi_eq = phi_in - (period * HT()) / TBF();
          if (m_FriedelFlag) return -phi_eq;
          return phi_eq;
        }
        /*! \brief Phase for input index, given phase for
            equivalent Miller index.
         */
        /*! Formula used:<br>
            if (FriedelFlag()) phi_eq = -phi_eq;<br>
            deg == 0: phi_in = phi_eq + (2 * pi * HT()) / TBF();<br>
            deg != 0: phi_in = phi_eq + (360 * HT()) / TBF();
         */
        template <class FloatType>
        FloatType phase_in(FloatType phi_eq, bool deg = false) const
        {
          if (m_FriedelFlag) phi_eq = -phi_eq;
          FloatType period = cctbx::constants::two_pi;
          if (deg) period = 360;
          return phi_eq + (period * HT()) / TBF();
        }

        /*! \brief Complex value for equivalent index, given complex
            value for input index.
         */
        /*! Formula used:<br>
            f_eq = f_in * exp(-2 * pi * j * HT() / TBF());<br>
            where j is the imaginary number.<br>
            if (FriedelFlag()) f_eq = conj(f_eq);
         */
        template <class FloatType>
        std::complex<FloatType>
        complex_eq(const std::complex<FloatType>& f_in) const
        {
          FloatType theta = (-cctbx::constants::two_pi * HT()) / TBF();
          std::complex<FloatType>
          f_eq = f_in * std::polar(FloatType(1), theta);
          if (m_FriedelFlag) return std::conj(f_eq);
          return f_eq;
        }
        /*! \brief Complex value for input index, given complex
            value for equivalent index.
         */
        /*! Formula used:<br>
            if (FriedelFlag()) f_eq = conj(f_eq);<br>
            f_in = f_eq * exp(2 * pi * j * HT() / TBF());<br>
            where j is the imaginary number.
         */
        template <class FloatType>
        std::complex<FloatType>
        complex_in(std::complex<FloatType> f_eq) const
        {
          if (m_FriedelFlag) f_eq = std::conj(f_eq);
          FloatType theta = ( cctbx::constants::two_pi * HT()) / TBF();
          return f_eq * std::polar(FloatType(1), theta);
        }

      protected:
        Index m_HR;
        int   m_HT;
        int   m_TBF;
        bool  m_FriedelFlag;
    };

  } // namespace Miller

  namespace sgtbx {

#ifndef DOXYGEN_SHOULD_SKIP_THIS

    inline Miller::Index
    operator*(const Miller::Index& lhs, const RotMx& rhs) {
      return Miller::Index(
        lhs[0] * rhs[0] + lhs[1] * rhs[3] + lhs[2] * rhs[6],
        lhs[0] * rhs[1] + lhs[1] * rhs[4] + lhs[2] * rhs[7],
        lhs[0] * rhs[2] + lhs[1] * rhs[5] + lhs[2] * rhs[8]);
    }

    inline int operator*(const Miller::Index& lhs, const TrVec& rhs) {
      int result = 0;
      for(int i=0;i<3;i++) result += lhs[i] * rhs[i];
      return result;
    }

    inline int HT_mod_1(const Miller::Index& H, const TrVec& T) {
      return sgtbx::modPositive(H * T, T.BF());
    }

    class SpaceGroup; // forward declaration

#endif // DOXYGEN_SHOULD_SKIP_THIS

    //! XXX merge with PhaseRestriction
    class sys_absent_test
    {
      public:
        //! XXX
        sys_absent_test() {}
        //! XXX
        sys_absent_test(const SpaceGroup& sgops, const Miller::Index& h);
        //! XXX
        int ht_restriction() const { return ht_restriction_; }
        //! XXX
        bool is_sys_absent() const { return ht_restriction_ == -2; }
        //! XXX
        bool is_centric() const { return ht_restriction_ >= 0; }
      protected:
        int ht_restriction_;
    };

    //! class for the high-level handling of centric reflections.
    /*! A reflection with the Miller index H is "centric" if
        there is a symmetry operation with rotation part R such
        that H*R = -H.<br>
        The phase of a centric reflection is restricted to two phase
        angels (modulo pi).
     */
    class PhaseRestriction {
      public:
        //! Default constructor. Some data members are not initialized!
        PhaseRestriction() {}
        //! For internal use only.
        PhaseRestriction(int HT, int TBF) : m_HT(HT), m_TBF(TBF) {}

        //! Test if there actually is a phase restriction.
        /*! See class details.
         */
        bool isCentric() const { return m_HT >= 0; }

        //! Phase shift H*T (mod 1) corresponding to H*R = -H.
        /*! Low-level information for computing the restricted phases.
            HT() is multiplied by a base factor TBF() in order to obtain
            an integer value.
            <p>
            See also: HT_angle()
         */
        int HT() const { return m_HT; }
        //! Translation base factor.
        /*! This is the factor by which HT() is multiplied.
         */
        int TBF() const { return m_TBF; }

        //! Phase restriction in radians or degrees.
        /*! The return value is -1 if the phase is not restricted,
            and >= 0 and < pi or 180 otherwise.
         */
        double HT_angle(bool deg = false) const
        {
          if (deg) return HT_angle_(180.);
          return HT_angle_(cctbx::constants::pi);
        }

        /*! \brief Test if phase phi (with given Period) is
            compatible with restriction.
         */
        //! Test if phase phi is compatible with restriction.
        /*! The tolerance compensates for rounding errors.
         */
        bool isValidPhase(
          double phi, bool deg = false, double tolerance = 1.e-5) const
        {
          if (deg) return isValidPhase_(180., phi, tolerance);
          return isValidPhase_(cctbx::constants::pi, phi, tolerance);
        }

      private:
        double HT_angle_(double Period) const {
          if (!isCentric()) return -1.;
          return Period * double(m_HT) / double(m_TBF);
        }

        bool isValidPhase_(double Period, double phi, double tolerance) const;

        int m_HT;
        int m_TBF;
    };

    //! class for the handling of symmetrically equivalent Miller indices.
    /*! This class is exclusively used to represent the results
        of SpaceGroup::getEquivMillerIndices().<br>
        The Miller index used in the call to getEquivMillerIndices
        is referred to as the "input Miller index."
     */
    class SymEquivMillerIndices
    {
      public:
        //! Default constructor. Some data members are not initialized!
        SymEquivMillerIndices() {}
        //! The phase restriction (if any) for the input Miller index.
        /*! See class PhaseRestriction.
         */
        PhaseRestriction getPhaseRestriction() const {
          return PhaseRestriction(m_HT_Restriction, m_TBF); }
        //! Test if reflection with input Miller index is centric.
        /*! A reflection with the Miller index H is "centric" if
            there is a symmetry operation with rotation part R such
            that H*R = -H.<br>
            See also: class PhaseRestriction
         */
        bool isCentric() const { return m_HT_Restriction >= 0; }
        //! Number of symmetrically equivalent Miller indices.
        /*! Note that this is not in general equal to the multiplicity.<br>
            See also: M()
         */
        int N() const { return m_List.size(); }
        //! Multiplicity of the input Miller index.
        /*! For acentric reflections and in the presence of Friedel symmetry
            (no anomalous signal), the multiplicity is twice the number
            of symmetrically equivalent Miller indices N().<br>
            For centric reflections or in the absence of Friedel symmetry
            (i.e. in the presence of an anomalous signal), the multiplicity
            is equal to the number of symmetrically equivalent Miller indices
            N().<br>
            See also: N()
         */
        int M(bool FriedelFlag) const {
          if (FriedelFlag && !isCentric()) return 2 * N();
          return N();
        }
        //! XXX
        int n_p1_listing(bool FriedelFlag) const {
          if (FriedelFlag && isCentric()) return N() / 2;
          return N();
        }
        //! Flag for Friedel mates == M(FriedelFlag)/N().
        /*! Useful for looping over all symmetrically equivalent reflections
            including Friedel mates (if FriedelFlag == true).<br>
            See also: operator()
         */
        int fMates(bool FriedelFlag) const {
          if (FriedelFlag && !isCentric()) return 2;
          return 1;
        }
        //! Determine "epsilon" for the given Miller index.
        /*! The factor epsilon counts the number of times a Miller
            index H is mapped onto itself by symmetry. This factor
            is used for "statistical averaging" and in direct methods
            formulae.<br>
            Note that epsilon is directly related to the number
            of symmetrically equivalent indices N():<br>
            epsilon == sgtbx::SpaceGroup::OrderP() / N()
         */
        int epsilon() const { return m_OrderP / N(); }

        /*! \brief Low-level access to the N() symmetrically
            equivalent Miller indices.
         */
        /*! See also: operator()
         */
        const Miller::SymEquivIndex& operator[](int iList) const {
          return m_List[iList];
        }
        //! Medium-level access to the symmetrically equivalent Miller indices.
        /*! Intended use:<pre>
            sgtbx::SpaceGroup SgOps = ... // define space group
            Miller::Index H = ... // define input Miller index.
            bool FriedelFlag = ... // define Friedel symmetry.
            sgtbx::SymEquivMillerIndices SEMI = SgOps.getEquivMillerIndices(H);
            for (int iList = 0; iList < SEMI.N(); iList++)
              for (int iMate = 0; iMate < SEMI.fMates(FriedelFlag); iMate++)
                Miller::Index EquivH = SEMI(iMate, iList);
            </pre>
            Note that it is possible and often more convenient to have a
            one-deep loop with M() iterations.<br>
            See also: operator()(int iIL)
         */
        Miller::SymEquivIndex operator()(int iMate, int iList) const;
        //! High-level access to the symmetrically equivalent Miller indices.
        /*! Intended use:<pre>
            sgtbx::SpaceGroup SgOps = ... // define space group
            Miller::Index H = ... // define input Miller index.
            bool FriedelFlag = ... // define Friedel symmetry.
            sgtbx::SymEquivMillerIndices SEMI = SgOps.getEquivMillerIndices(H);
            for (int iIL = 0; iIL < SEMI.M(FriedelFlag); iIL++)
              Miller::Index EquivH = SEMI(iIL);
            </pre>
         */
        Miller::SymEquivIndex operator()(int iIL) const;

        //! Test if phase phi is compatible with restriction.
        /*! The tolerance compensates for rounding errors.<br>
            See also: class PhaseRestriction
         */
        bool isValidPhase(double phi,
                          bool deg = false,
                          double tolerance = 1.e-5) const {
          return getPhaseRestriction().isValidPhase(phi, deg, tolerance);
        }
      private:
        int m_TBF;
        int m_OrderP;
        int m_HT_Restriction;
        std::vector<Miller::SymEquivIndex> m_List;
        SymEquivMillerIndices(int TBF, int OrderP)
          : m_TBF(TBF), m_OrderP(OrderP), m_HT_Restriction(-1), m_List() {}
        void add(const Miller::SymEquivIndex& SEI);
        void sort_in_hemispheres();
#ifndef DOXYGEN_SHOULD_SKIP_THIS
        friend class SpaceGroup;
#endif // DOXYGEN_SHOULD_SKIP_THIS
        struct iIL_decomposition
        {
          iIL_decomposition(int iMate_, int iList_)
            : iMate(iMate_), iList(iList_)
          {}
          int iMate, iList;
        };
        iIL_decomposition decompose_iIL(int iIL) const;
    };

  } // namespace sgtbx
} // namespace cctbx

#endif // CCTBX_SGTBX_MILLER_H
