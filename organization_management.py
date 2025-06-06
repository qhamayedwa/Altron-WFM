"""
Organizational Hierarchy Management
Provides management interface for Company → Regions → Sites → Departments → People
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db
from models import Company, Region, Site, Department, User
from auth import role_required
from datetime import datetime

org_bp = Blueprint('organization', __name__, url_prefix='/organization')

@org_bp.route('/dashboard')
@login_required
@role_required('Super User', 'Admin', 'HR Manager')
def dashboard():
    """Organizational hierarchy dashboard"""
    companies = Company.query.filter_by(is_active=True).all()
    
    # Get statistics
    stats = {
        'total_companies': Company.query.filter_by(is_active=True).count(),
        'total_regions': Region.query.filter_by(is_active=True).count(),
        'total_sites': Site.query.filter_by(is_active=True).count(),
        'total_departments': Department.query.filter_by(is_active=True).count(),
        'total_employees': User.query.filter_by(is_active=True).count()
    }
    
    return render_template('organization/dashboard.html', 
                         companies=companies, stats=stats)

# Company Management
@org_bp.route('/companies')
@login_required
@role_required('Super User', 'Admin')
def companies():
    """List all companies"""
    companies = Company.query.all()
    return render_template('organization/companies.html', companies=companies)

@org_bp.route('/companies/create', methods=['GET', 'POST'])
@login_required
@role_required('Super User', 'Admin')
def create_company():
    """Create a new company"""
    if request.method == 'POST':
        company = Company(
            name=request.form['name'],
            code=request.form['code'],
            legal_name=request.form.get('legal_name'),
            registration_number=request.form.get('registration_number'),
            tax_number=request.form.get('tax_number'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            website=request.form.get('website'),
            address_line1=request.form.get('address_line1'),
            address_line2=request.form.get('address_line2'),
            city=request.form.get('city'),
            state_province=request.form.get('state_province'),
            postal_code=request.form.get('postal_code'),
            country=request.form.get('country', 'South Africa'),
            timezone=request.form.get('timezone', 'Africa/Johannesburg'),
            currency=request.form.get('currency', 'ZAR'),
            fiscal_year_start=int(request.form.get('fiscal_year_start', 4))
        )
        
        try:
            db.session.add(company)
            db.session.commit()
            flash('Company created successfully!', 'success')
            return redirect(url_for('organization.companies'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating company: {str(e)}', 'error')
    
    return render_template('organization/create_company.html')

@org_bp.route('/companies/<int:company_id>')
@login_required
@role_required('Super User', 'Admin', 'HR Manager')
def view_company(company_id):
    """View company details with hierarchy"""
    company = Company.query.get_or_404(company_id)
    regions = Region.query.filter_by(company_id=company_id, is_active=True).all()
    
    # Get company statistics
    stats = {
        'regions': Region.query.filter_by(company_id=company_id, is_active=True).count(),
        'sites': db.session.query(Site).join(Region).filter(
            Region.company_id == company_id, Site.is_active == True).count(),
        'departments': db.session.query(Department).join(Site).join(Region).filter(
            Region.company_id == company_id, Department.is_active == True).count(),
        'employees': db.session.query(User).filter(User.is_active == True).count()
    }
    
    return render_template('organization/view_company.html', 
                         company=company, regions=regions, stats=stats)

@org_bp.route('/companies/<int:company_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('Super User', 'Admin')
def edit_company(company_id):
    """Edit company details"""
    company = Company.query.get_or_404(company_id)
    
    if request.method == 'POST':
        company.name = request.form['name']
        company.code = request.form['code']
        company.legal_name = request.form.get('legal_name')
        company.registration_number = request.form.get('registration_number')
        company.tax_number = request.form.get('tax_number')
        company.email = request.form.get('email')
        company.phone = request.form.get('phone')
        company.website = request.form.get('website')
        company.address_line1 = request.form.get('address_line1')
        company.address_line2 = request.form.get('address_line2')
        company.city = request.form.get('city')
        company.state_province = request.form.get('state_province')
        company.postal_code = request.form.get('postal_code')
        company.country = request.form.get('country', 'South Africa')
        company.timezone = request.form.get('timezone', 'Africa/Johannesburg')
        company.currency = request.form.get('currency', 'ZAR')
        company.fiscal_year_start = int(request.form.get('fiscal_year_start', 4))
        company.updated_at = datetime.utcnow()
        
        try:
            db.session.commit()
            flash('Company updated successfully!', 'success')
            return redirect(url_for('organization.view_company', company_id=company_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating company: {str(e)}', 'error')
    
    return render_template('organization/edit_company.html', company=company)

# Region Management
@org_bp.route('/companies/<int:company_id>/regions/create', methods=['GET', 'POST'])
@login_required
@role_required('Super User', 'Admin', 'HR Manager')
def create_region(company_id):
    """Create a new region for a company"""
    company = Company.query.get_or_404(company_id)
    
    if request.method == 'POST':
        # Handle manager selection - either from dropdown or manual entry
        manager_id = request.form.get('manager_select')
        manager_name = request.form.get('manager_name')
        
        # If manager selected from dropdown, get their details
        if manager_id:
            selected_manager = User.query.get(manager_id)
            if selected_manager:
                manager_name = selected_manager.full_name
                email = request.form.get('email') or selected_manager.email
                phone = request.form.get('phone') or selected_manager.phone_number or selected_manager.mobile_number
            else:
                email = request.form.get('email')
                phone = request.form.get('phone')
        else:
            email = request.form.get('email')
            phone = request.form.get('phone')
        
        region = Region(
            company_id=company_id,
            name=request.form['name'],
            code=request.form['code'],
            description=request.form.get('description'),
            manager_name=manager_name,
            email=email,
            phone=phone,
            address_line1=request.form.get('address_line1'),
            address_line2=request.form.get('address_line2'),
            city=request.form.get('city'),
            state_province=request.form.get('state_province'),
            postal_code=request.form.get('postal_code'),
            timezone=request.form.get('timezone')
        )
        
        try:
            db.session.add(region)
            db.session.commit()
            flash('Region created successfully!', 'success')
            return redirect(url_for('organization.view_company', company_id=company_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating region: {str(e)}', 'error')
    
    # Get potential managers from active users
    managers = User.query.filter_by(is_active=True).all()
    
    return render_template('organization/create_region.html', 
                         company=company, managers=managers)

@org_bp.route('/regions/<int:region_id>')
@login_required
@role_required('Super User', 'Admin', 'HR Manager')
def view_region(region_id):
    """View region details with sites"""
    region = Region.query.get_or_404(region_id)
    sites = Site.query.filter_by(region_id=region_id, is_active=True).all()
    
    # Get region statistics
    stats = {
        'sites': Site.query.filter_by(region_id=region_id, is_active=True).count(),
        'departments': db.session.query(Department).join(Site).filter(
            Site.region_id == region_id, Department.is_active == True).count(),
        'employees': db.session.query(User).filter(User.is_active == True).count()
    }
    
    return render_template('organization/view_region.html', 
                         region=region, sites=sites, stats=stats)

# Site Management
@org_bp.route('/regions/<int:region_id>/sites/create', methods=['GET', 'POST'])
@login_required
@role_required('Super User', 'Admin', 'HR Manager')
def create_site(region_id):
    """Create a new site for a region"""
    region = Region.query.get_or_404(region_id)
    
    if request.method == 'POST':
        site = Site(
            region_id=region_id,
            name=request.form['name'],
            code=request.form['code'],
            site_type=request.form.get('site_type'),
            description=request.form.get('description'),
            manager_name=request.form.get('manager_name'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            address_line1=request.form['address_line1'],
            address_line2=request.form.get('address_line2'),
            city=request.form['city'],
            state_province=request.form.get('state_province'),
            postal_code=request.form.get('postal_code'),
            latitude=float(request.form['latitude']) if request.form.get('latitude') else None,
            longitude=float(request.form['longitude']) if request.form.get('longitude') else None,
            geo_fence_radius=int(request.form.get('geo_fence_radius', 100)),
            timezone=request.form.get('timezone'),
            allow_remote_work=bool(request.form.get('allow_remote_work'))
        )
        
        # Parse operating hours
        if request.form.get('operating_hours_start'):
            site.operating_hours_start = datetime.strptime(
                request.form['operating_hours_start'], '%H:%M').time()
        if request.form.get('operating_hours_end'):
            site.operating_hours_end = datetime.strptime(
                request.form['operating_hours_end'], '%H:%M').time()
        
        try:
            db.session.add(site)
            db.session.commit()
            flash('Site created successfully!', 'success')
            return redirect(url_for('organization.view_region', region_id=region_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating site: {str(e)}', 'error')
    
    # Get potential managers (active users who could be site managers)
    potential_managers = User.query.filter_by(is_active=True).all()
    
    return render_template('organization/create_site.html', 
                         region=region, potential_managers=potential_managers)

@org_bp.route('/sites/<int:site_id>')
@login_required
@role_required('Super User', 'Admin', 'HR Manager')
def view_site(site_id):
    """View site details with departments"""
    site = Site.query.get_or_404(site_id)
    departments = Department.query.filter_by(site_id=site_id, is_active=True).all()
    
    # Get site statistics
    stats = {
        'departments': Department.query.filter_by(site_id=site_id, is_active=True).count(),
        'employees': db.session.query(User).filter(User.is_active == True).count()
    }
    
    return render_template('organization/view_site.html', 
                         site=site, departments=departments, stats=stats)

# Department Management
@org_bp.route('/sites/<int:site_id>/departments/create', methods=['GET', 'POST'])
@login_required
@role_required('Super User', 'Admin', 'HR Manager')
def create_department(site_id):
    """Create a new department for a site"""
    site = Site.query.get_or_404(site_id)
    
    if request.method == 'POST':
        department = Department(
            site_id=site_id,
            name=request.form['name'],
            code=request.form['code'],
            description=request.form.get('description'),
            cost_center=request.form.get('cost_center'),
            budget_code=request.form.get('budget_code'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            extension=request.form.get('extension'),
            standard_hours_per_day=float(request.form.get('standard_hours_per_day', 8.0)),
            standard_hours_per_week=float(request.form.get('standard_hours_per_week', 40.0))
        )
        
        # Set managers if provided
        if request.form.get('manager_id'):
            department.manager_id = int(request.form['manager_id'])
        if request.form.get('deputy_manager_id'):
            department.deputy_manager_id = int(request.form['deputy_manager_id'])
        
        try:
            db.session.add(department)
            db.session.commit()
            flash('Department created successfully!', 'success')
            return redirect(url_for('organization.view_site', site_id=site_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating department: {str(e)}', 'error')
    
    # Get potential managers
    managers = User.query.filter_by(is_active=True).all()
    
    return render_template('organization/create_department.html', 
                         site=site, managers=managers)

@org_bp.route('/departments/<int:department_id>')
@login_required
@role_required('Super User', 'Admin', 'HR Manager', 'Manager')
def view_department(department_id):
    """View department details with employees"""
    department = Department.query.get_or_404(department_id)
    employees = User.query.filter_by(department_id=department_id, is_active=True).all()
    
    # Get department statistics
    stats = {
        'employees': len(employees),
        'full_time': len([e for e in employees if e.employment_type == 'full_time']),
        'part_time': len([e for e in employees if e.employment_type == 'part_time']),
        'contractors': len([e for e in employees if e.employment_type == 'contract'])
    }
    
    return render_template('organization/view_department.html', 
                         department=department, employees=employees, stats=stats)

# API Endpoints
@org_bp.route('/api/hierarchy/<int:company_id>')
@login_required
def api_company_hierarchy(company_id):
    """Get complete hierarchy for a company"""
    company = Company.query.get_or_404(company_id)
    
    hierarchy = {
        'company': {
            'id': company.id,
            'name': company.name,
            'code': company.code
        },
        'regions': []
    }
    
    for region in company.regions.filter_by(is_active=True):
        region_data = {
            'id': region.id,
            'name': region.name,
            'code': region.code,
            'sites': []
        }
        
        for site in region.sites.filter_by(is_active=True):
            site_data = {
                'id': site.id,
                'name': site.name,
                'code': site.code,
                'departments': []
            }
            
            for dept in site.departments.filter_by(is_active=True):
                dept_data = {
                    'id': dept.id,
                    'name': dept.name,
                    'code': dept.code,
                    'employee_count': dept.employees.filter_by(is_active=True).count()
                }
                site_data['departments'].append(dept_data)
            
            region_data['sites'].append(site_data)
        
        hierarchy['regions'].append(region_data)
    
    return jsonify(hierarchy)

@org_bp.route('/api/search')
@login_required
def api_search():
    """Search across organizational hierarchy"""
    query = request.args.get('q', '')
    if len(query) < 2:
        return jsonify({'results': []})
    
    results = []
    
    # Search companies
    companies = Company.query.filter(
        Company.name.ilike(f'%{query}%'),
        Company.is_active == True
    ).limit(5).all()
    
    for company in companies:
        results.append({
            'type': 'company',
            'id': company.id,
            'name': company.name,
            'code': company.code,
            'url': url_for('organization.view_company', company_id=company.id)
        })
    
    # Search regions
    regions = Region.query.filter(
        Region.name.ilike(f'%{query}%'),
        Region.is_active == True
    ).limit(5).all()
    
    for region in regions:
        results.append({
            'type': 'region',
            'id': region.id,
            'name': region.name,
            'code': region.code,
            'company': region.company.name,
            'url': url_for('organization.view_region', region_id=region.id)
        })
    
    # Search sites
    sites = Site.query.filter(
        Site.name.ilike(f'%{query}%'),
        Site.is_active == True
    ).limit(5).all()
    
    for site in sites:
        results.append({
            'type': 'site',
            'id': site.id,
            'name': site.name,
            'code': site.code,
            'region': site.region.name,
            'url': url_for('organization.view_site', site_id=site.id)
        })
    
    # Search departments
    departments = Department.query.filter(
        Department.name.ilike(f'%{query}%'),
        Department.is_active == True
    ).limit(5).all()
    
    for dept in departments:
        results.append({
            'type': 'department',
            'id': dept.id,
            'name': dept.name,
            'code': dept.code,
            'site': dept.site.name,
            'url': url_for('organization.view_department', department_id=dept.id)
        })
    
    return jsonify({'results': results})