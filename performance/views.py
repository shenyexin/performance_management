from django.shortcuts import render, HttpResponse, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from datetime import datetime
from .models import MonthlySalesData
from .models import QuarterlySalesData
from .models import InternalControlIndicators
from .models import ConstantData
from .models import MonthlyPerformance
from .models import QuarterlyPerformance
from .models import MonthlyFormula
from .models import QuarterlyFormula
from .models import User
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from .forms import cleaned_formula
from .utils import UploadTable
from .utils import ExportTable
from .utils import CalcuteMonthlyPerformance
from .utils import CalculateQuarterlyPerformance
from .utils.Paginator import PageInfo


@login_required
def index(request):
    return render(request, '首页.html')


# 测试页面方法
def test_page(request):
    return render(request, '报表公式修改-管理层月度绩效考核结果.html')


# 登陆方法
def user_login(request):
    if request.method == 'GET':
        return render(request, '登录.html')
    else:
        # 从前端获取用户名密码
        username = request.POST.get('username')
        password = request.POST.get('password')

        # 验证登录信息
        user = authenticate(username=username, password=password)
        if user:
            # 登录成功，记录登录信息，重定向首页
            login(request, user)
            return redirect('index')
        else:
            # 登录失败，写入用户名密码错误信息并重载页面
            messages.error(request, '用户名或密码错误')
            return redirect('user_login')


# 登出方法
@login_required
def user_logout(request):
    # 登出用户
    logout(request)
    # 重定向登录页面
    return redirect('user_login')


# 展示账号管理页面方法
def user_management(request):
    # 获取所有用户信息
    users = User.objects.all()
    # 打包信息
    context = {
        'users': users,
    }
    # 引导前端页面
    return render(request, '账号权限管理-账号管理.html', context=context)


# 新增账号方法
def add_user(request):
    # 从前端获取填写用户信息
    job_number = str(request.POST.get('job_number'))
    name = str(request.POST.get('name'))
    department = str(request.POST.get('department'))
    telephone = str(request.POST.get('telephone'))
    password = str(request.POST.get('password'))

    # 保存用户
    try:
        user = User.objects.create_user(
            username=job_number,
            password=password,
            last_name=name,
        )
        user.extension.job_number = job_number
        user.extension.department = department
        user.extension.telephone = telephone
        user.save()
        # 写入成功提示
        messages.success(request, '用户增加成功')
    except:
        # 写入失败提示
        messages.error(request, '用户增加失败')
    # 重载账号展示页面
    return redirect('user_management')


# 删除账号方法
def delete_user(request):
    # 防止把自己删除
    # 先获取当前登录用户id
    current_user_id = str(User.objects.get(id=request.user.id).id)
    # GET为多条删除，POST为单条删除
    if request.method == 'GET':
        delete_id = request.GET.getlist('delete_id', [])
        # 判断当前用户是否在列表中
        # 在的话就直接提示不能删自己
        if current_user_id in delete_id:
            messages.error(request, '不可以删除当前登录的账号')
            return HttpResponse('success')
        # 遍历删除
        for id in delete_id:
            User.objects.get(id=id).delete()
        # 写入删除成功提示
        messages.success(request, '选中用户删除成功')
        # 返回成功
        return HttpResponse('success')
    else:
        # 取得要删除的id
        delete_id = request.POST.get('delete_id')
        # 判断要删除的是不是当前用户
        # 是的话直接提示不能删自己
        if current_user_id == delete_id:
            messages.error(request, '不能删除当前登录账号')
            return redirect('user_management')
        # 从数据库中删除
        User.objects.get(id=delete_id).delete()
        # 写入删除成功提示
        messages.success(request, '用户删除成功')
    # 重载账号展示页面
    return redirect('user_management')


# 修改账户方法
def change_user(request):
    # 从前端获取要修改的id
    change_id = request.POST.get('change_id')
    # 获取修改后的信息
    job_number = request.POST.get('job_number')
    name = request.POST.get('name')
    department = request.POST.get('department')
    telephone = request.POST.get('telephone')
    # 取出此账户并更新信息
    user = User.objects.get(id=change_id)
    user.extension.job_number = job_number
    user.last_name = name
    user.extension.department = department
    user.extension.telephone = telephone
    user.save()
    # 写入成功提示
    messages.success(request, '用户信息修改成功')
    # 重载账号展示页面
    return redirect('user_management')


# 展示角色权限管理界面
def group_management(request):
    # 从数据库中取出所有角色(组)
    groups = Group.objects.all()
    # 从数据库中取出所有账号
    users = User.objects.all()
    # 打包数据
    context = {
        'groups': groups,
        'users': users,
    }
    return render(request, '账号权限管理-权限管理.html', context=context)


# 增加角色方法
def add_group(request):
    # 取得角色名称
    name = request.POST.get('name')
    # 取得权限列表
    permissions = request.POST.getlist('permissions', [])
    # 判断前三张表有没有只有管理没查看的权限
    # 如果存在这种情况，将相应的查看权限补充上
    # 月度营业数据
    if 'manage_monthly_sales_data' in permissions and 'view_monthly_sales_data' not in permissions:
        permissions.append('view_monthly_sales_data')
    # 季度营业数据
    if 'manage_quarterly_sales_data' in permissions and 'view_quarterly_sales_data' not in permissions:
        permissions.append('view_quarterly_sales_data')
    # 内控指标汇总
    if 'manage_internal_control_indicators' in permissions and 'view_internal_control_indicators' not in permissions:
        permissions.append('view_internal_control_indicators')
    # 从权限表中取出相应的权限
    permissions_list = Permission.objects.filter(codename__in=permissions)

    # 创建角色(组)
    group = Group.objects.get_or_create(name=name)[0]
    # 给新角色加权限
    group.permissions.add(*permissions_list)
    # 写入成功信息
    messages.success(request, '角色增加成功')
    # 重载角色权限管理界面
    return redirect('group_management')


# 删除角色方法
def delete_group(request):
    # get为多选删除，post为单条删除
    if request.method == 'GET':
        delete_id = request.GET.getlist('delete_id', [])
        # 遍历删除
        for id in delete_id:
            Group.objects.get(id=id).delete()
        # 写入删除成功提示
        messages.success(request, '选中角色删除成功')
        # 返回成功
        return HttpResponse('success')
    else:
        delete_id = request.POST.get('delete_id')
        # 从数据库中删除
        Group.objects.get(id=delete_id).delete()
        # 写入删除成功提示
        messages.success(request, '角色删除成功')
        # 重载页面
        return redirect('group_management')


# 修改角色方法
def change_group(request):
    # 获取要修改的id
    change_id = request.POST.get('change_id')
    # 获取更改后的权限列表
    permissions = request.POST.getlist('permissions')
    # 取出相应的权限
    permissions_list = Permission.objects.filter(codename__in=permissions)
    # 获取要修改的角色(组)
    group = Group.objects.get(id=change_id)
    # 清空当前权限
    group.permissions.clear()
    # 给当前角色(组)重新赋予权限
    group.permissions.add(*permissions_list)
    # 写入成功信息
    messages.success(request, '角色权限修改成功')
    # 重载角色权限管理界面
    return redirect('group_management')


# 从角色(组)批量赋予给账号方法
def group_to_user(request):
    # 判断有无ajax变量值，有的话就是提交数据，没有就是访问页面
    if not request.GET.get('ajax'):
        # 获取角色(组)的id
        group_id = request.GET.get('group_id')
        group = Group.objects.get(id=group_id)
        # 获取这个角色下的账号
        in_group_users = group.user_set.all()
        # 获取所有用户
        users = User.objects.all()
        # 筛选出未在此角色(组)的用户列表
        out_group_user = users
        for user in in_group_users:
            out_group_user = out_group_user.exclude(id=user.id)
        # 打包数据
        context = {
            'group_id': group_id,
            'in_group_users': in_group_users,
            'out_group_users': out_group_user,
        }
        # 引导前端页面
        return render(request, '账号权限管理-权限管理-赋予用户角色.html', context=context)
    else:
        # 获取组id并取出这个组
        group_id = request.GET.get('group_id')
        group = Group.objects.get(id=group_id)
        # 获取选择的账号id列表
        user_id_list = request.GET.getlist('selected', [])

        # 将这个组的用户清空
        in_group_users = group.user_set.all()
        for user in in_group_users:
            user.groups.remove(group)

        # 将这些用户加入到这个组中去
        # 选出这些用户
        users = User.objects.filter(id__in=user_id_list)
        # 将这些用户加入到这个组里
        for user in users:
            user.groups.add(group)
        # 写入成功提示
        messages.success(request, '赋予角色成功')

        return HttpResponse('success')


# 展示月度营业数据方法
@login_required
def show_monthly_sales_data(request):
    # 从数据库中取出所有数据
    monthly_sales_data = MonthlySalesData.objects.all()
    # 打包数据
    context = {
        'monthly_sales_data': monthly_sales_data,
    }
    # 引导前端页面
    return render(request, '业务数据管理-月度营业数据.html', context=context)


# 增加月度营业数据方法
@login_required
def add_monthly_sales_data(request):
    # 从前端获取数据
    year = request.POST.get('year')
    month = request.POST.get('month')
    turnover = request.POST.get('turnover')
    operating_expenses = request.POST.get('operating_expenses')
    amount_repaid = request.POST.get('amount_repaid')
    inventory = request.POST.get('inventory')
    profit = request.POST.get('profit')

    # 转换日期对象
    # date = datetime(year=year, month=month, day=1, hour=1, minute=1, second=1)

    # 写入数据库
    MonthlySalesData.objects.create(
        year=year,
        month=month,
        turnover=turnover,
        operating_expenses=operating_expenses,
        amount_repaid=amount_repaid,
        inventory=inventory,
        profit=profit,
    )

    # 写入成功提示
    messages.success(request, '数据添加成功')

    # 重定向展示页面
    return redirect('show_monthly_sales_data')


# 删除月度营业数据方法
@login_required
def delete_monthly_sales_data(request):
    # get为多选删除，post为单条删除
    if request.method == 'GET':
        delete_id = request.GET.getlist('delete_id', [])
        # 遍历删除
        for id in delete_id:
            MonthlySalesData.objects.get(id=id).delete()
        # 写入删除成功提示
        messages.success(request, '选中数据删除成功')
        # 返回成功
        return HttpResponse('success')
    else:
        delete_id = request.POST.get('delete_id')
        # 从数据库中删除
        MonthlySalesData.objects.get(id=delete_id).delete()
        # 写入删除成功提示
        messages.success(request, '数据删除成功')
        # 重载页面
        return redirect('show_monthly_sales_data')


# 修改月度营业数据
@login_required
def change_monthly_sales_data(request):
    # 从前端获取要修改的id
    change_id = request.POST.get('change_id')
    # 从前端获取修改后的数据
    # change_date_month = int(request.POST.get('change_date_month'))
    change_year = request.POST.get('change_year')
    change_month = request.POST.get('change_month')
    change_turnover = request.POST.get('change_turnover')
    change_operating_expenses = request.POST.get('change_operating_expenses')
    change_amount_repaid = request.POST.get('change_amount_repaid')
    change_inventory = request.POST.get('change_inventory')
    change_profit = request.POST.get('change_profit')

    # 转换日期对象
    # change_date = datetime(year=change_year, month=change_month, day=1, hour=1, minute=1, second=1)

    # 从数据库中取出该数据
    data = MonthlySalesData.objects.get(id=change_id)
    # 修改数据
    data.year = change_year
    data.month = change_month
    data.turnover = change_turnover
    data.operating_expenses = change_operating_expenses
    data.amount_repaid = change_amount_repaid
    data.inventory = change_inventory
    data.profit = change_profit
    # 保存更改
    data.save()

    # 写入数据修改成功
    messages.success(request, '数据修改成功')

    # 重定向展示页面
    return redirect('show_monthly_sales_data')


# 展示季度营业数据方法
@login_required
def show_quarterly_sales_data(request):
    # 从数据库中取出所有数据
    quarterly_sales_data = QuarterlySalesData.objects.all()
    # 打包数据
    context = {
        'quarterly_sales_data': quarterly_sales_data,
    }
    # 引导前端页面
    return render(request, '业务数据管理-季度营业数据.html', context=context)


# 增加季度营业数据方法
@login_required
def add_quarterly_sales_data(request):
    # 从前端获取数据
    year = int(request.POST.get('year'))
    quarter = int(request.POST.get('quarter'))
    turnover = request.POST.get('turnover')
    operating_expenses = request.POST.get('operating_expenses')
    amount_repaid = request.POST.get('amount_repaid')
    inventory = request.POST.get('inventory')
    profit = request.POST.get('profit')

    # 写入数据库
    QuarterlySalesData.objects.create(
        year=year,
        quarter=quarter,
        turnover=turnover,
        operating_expenses=operating_expenses,
        amount_repaid=amount_repaid,
        inventory=inventory,
        profit=profit,
    )

    # 写入成功提示
    messages.success(request, '数据增加成功')

    # 重定向展示页面
    return redirect('show_quarterly_sales_data')


# 删除季度营业数据方法
@login_required
def delete_quarterly_sales_data(request):
    # get为多选删除，post为单条删除
    if request.method == 'GET':
        delete_id = request.GET.getlist('delete_id', [])
        # 遍历删除
        for id in delete_id:
            QuarterlySalesData.objects.get(id=id).delete()
        # 写入删除成功提示
        messages.success(request, '选中数据删除成功')
        # 返回成功
        return HttpResponse('success')
    else:
        delete_id = request.POST.get('delete_id')
        # 从数据库中删除
        QuarterlySalesData.objects.get(id=delete_id).delete()
        # 写入数据删除成功提示
        messages.success(request, '数据删除成功')
        # 重载页面
        return redirect('show_quarterly_sales_data')


# 修改季度营业数据方法
@login_required
def change_quarterly_sales_data(request):
    # 从前端获取要修改的id
    change_id = request.POST.get('change_id')
    # 从前端获取修改后的数据
    change_turnover = request.POST.get('turnover')
    change_operating_expenses = request.POST.get('operating_expenses')
    change_amount_repaid = request.POST.get('amount_repaid')
    change_inventory = request.POST.get('inventory')
    change_profit = request.POST.get('profit')

    # 从数据库中取出该数据
    data = QuarterlySalesData.objects.get(id=change_id)
    # 修改数据
    # data.date = change_date
    data.turnover = change_turnover
    data.operating_expenses = change_operating_expenses
    data.amount_repaid = change_amount_repaid
    data.inventory = change_inventory
    data.profit = change_profit
    # 保存更改
    data.save()

    # 写入修改成功提示
    messages.success(request, '数据修改成功')

    # 重定向展示页面
    return redirect('show_quarterly_sales_data')


# 展示内控指标汇总表方法
@login_required
def show_internal_control_indicators(request):
    # 从数据库中取出所有数据
    internal_control_indicators = InternalControlIndicators.objects.all()
    # 打包数据
    context = {
        'internal_control_indicators': internal_control_indicators,
    }
    # 引导前端页面
    return render(request, '业务数据管理-内控指标汇总.html', context=context)


# 增加内控指标汇总表方法
@login_required
def add_internal_control_indicators(request):
    # 从前端获取数据
    date = request.POST.get('date')
    order_number = request.POST.get('order_number')
    scheduled_delivery = request.POST.get('scheduled_delivery')
    actual_delivery = request.POST.get('actual_delivery')
    finished_number = request.POST.get('finished_number')
    unfinished_number = request.POST.get('unfinished_number')
    target_well_done_rate = request.POST.get('target_well_done_rate')
    actual_well_done_rate = request.POST.get('actual_well_done_rate')
    month_medical_expenses = request.POST.get('month_medical_expenses')
    cost_per_wan = request.POST.get('cost_per_wan')
    field_management_compliance = request.POST.get('field_management_compliance')

    # 转换日期对象
    date_list = date.split('-')
    scheduled_delivery_list = scheduled_delivery.split('-')
    actual_delivery_list = actual_delivery.split('-')
    date = datetime(year=int(date_list[0]), month=int(date_list[1]), day=int(date_list[2]), hour=1, minute=1, second=1)
    scheduled_delivery = datetime(year=int(scheduled_delivery_list[0]), month=int(scheduled_delivery_list[1]),
                                  day=int(scheduled_delivery_list[2]), hour=1, minute=1, second=1)
    actual_delivery = datetime(year=int(actual_delivery_list[0]), month=int(actual_delivery_list[1]),
                               day=int(actual_delivery_list[2]), hour=1, minute=1, second=1)

    # 存入数据库
    InternalControlIndicators.objects.create(
        date=date,
        order_number=order_number,
        scheduled_delivery=scheduled_delivery,
        actual_delivery=actual_delivery,
        finished_number=finished_number,
        unfinished_number=unfinished_number,
        target_well_done_rate=target_well_done_rate,
        actual_well_done_rate=actual_well_done_rate,
        month_medical_expenses=month_medical_expenses,
        cost_per_wan=cost_per_wan,
        field_management_compliance=field_management_compliance,
    )

    # 写入数据增加成功提示
    messages.success(request, '数据增加成功')

    # 重定向展示页面
    return redirect('show_internal_control_indicators')


# 删除内控指标汇总表方法
@login_required
def delete_internal_control_indicators(request):
    # get为多选删除，post为单条删除
    if request.method == 'GET':
        delete_id = request.GET.getlist('delete_id', [])
        # 遍历删除
        for id in delete_id:
            InternalControlIndicators.objects.get(id=id).delete()
        # 写入数据删除成功提示
        messages.success(request, '选中数据删除成功')
        # 返回成功
        return HttpResponse('success')
    else:
        delete_id = request.POST.get('delete_id')
        # 从数据库中删除
        InternalControlIndicators.objects.get(id=delete_id).delete()
        # 写入数据删除成功提示
        messages.success(request, '数据删除成功')
        # 重载页面
        return redirect('show_internal_control_indicators')


# 修改内控指标汇总表方法
@login_required
def change_internal_control_indicators(request):
    # 从前端获取要修改的id
    change_id = request.POST.get('change_id')
    # 从前端获取修改后的数据
    change_date = request.POST.get('date')
    change_order_number = request.POST.get('order_number')
    change_scheduled_delivery = request.POST.get('scheduled_delivery')
    change_actual_delivery = request.POST.get('actual_delivery')
    change_finished_number = request.POST.get('finished_number')
    change_unfinished_number = request.POST.get('unfinished_number')
    change_target_well_done_rate = request.POST.get('target_well_done_rate')
    change_actual_well_done_rate = request.POST.get('actual_well_done_rate')
    change_month_medical_expenses = request.POST.get('month_medical_expenses')
    change_cost_per_wan = request.POST.get('cost_per_wan')
    change_field_management_compliance = request.POST.get('field_management_compliance')

    # 转换日期对象
    date_list = change_date.split('-')
    scheduled_delivery_list = change_scheduled_delivery.split('-')
    actual_delivery_list = change_actual_delivery.split('-')
    change_date = datetime(year=int(date_list[0]), month=int(date_list[1]), day=int(date_list[2]), hour=1, minute=1,
                           second=1)
    change_scheduled_delivery = datetime(year=int(scheduled_delivery_list[0]), month=int(scheduled_delivery_list[1]),
                                         day=int(scheduled_delivery_list[2]), hour=1, minute=1, second=1)
    change_actual_delivery = datetime(year=int(actual_delivery_list[0]), month=int(actual_delivery_list[1]),
                                      day=int(actual_delivery_list[2]), hour=1, minute=1, second=1)

    # 从数据库中取出该数据
    data = InternalControlIndicators.objects.get(id=change_id)
    # 修改数据
    data.date = change_date
    data.order_number = change_order_number
    data.scheduled_delivery = change_scheduled_delivery
    data.actual_delivery = change_actual_delivery
    data.finished_number = change_finished_number
    data.unfinished_number = change_unfinished_number
    data.target_well_done_rate = change_target_well_done_rate
    data.actual_well_done_rate = change_actual_well_done_rate
    data.month_medical_expenses = change_month_medical_expenses
    data.cost_per_wan = change_cost_per_wan
    data.field_management_compliance = change_field_management_compliance
    # 保存更改
    data.save()

    # 返回数据修改成功提示
    messages.success(request, '数据修改成功')

    # 重定向展示页面
    return redirect('show_internal_control_indicators')


# 传递月度营业数据接口方法
@login_required
def give_monthly_sales_data(request):
    # 从数据库中取出所有数据
    data = MonthlySalesData.objects.values()
    return JsonResponse(list(data), safe=False)


# 传递季度营业数据接口方法
@login_required
def give_quarterly_sales_data(request):
    # 从数据库中取出所有数据
    data = QuarterlySalesData.objects.values()
    return JsonResponse(list(data), safe=False)


# 传递内控制表汇总接口方法
def give_internal_control_indicators(request):
    # 从数据库中取出所有数据
    data = InternalControlIndicators.objects.values()
    return JsonResponse(list(data), safe=False)


# 上传月度营业数据表格方法
@login_required
def upload_monthly_performance(request):
    file_data = request.FILES.get('upload_file')
    result = UploadTable.upload_monthly_performance(file_data)
    if result == 0:
        # 写入导入成功提示
        messages.success(request, '导入成功')
        # 重定向数据展示页面
        return redirect('show_monthly_sales_data')
    else:
        # 写入相应的错误提示
        messages.error(request, result)
        # 重定向数据展示页面
        return redirect('show_monthly_sales_data')


# 上传季度营业数据表格方法
@login_required
def upload_quarterly_performance(request):
    file_data = request.FILES.get('upload_file')
    result = UploadTable.upload_quarterly_performance(file_data)
    if result == 0:
        # 写入导入成功提示
        messages.success(request, '导入成功')
        # 重定向数据展示页面
        return redirect('show_quarterly_sales_data')
    else:
        # 写入相应的错误提示
        messages.error(request, result)
        # 重定向数据展示页面
        return redirect('show_quarterly_sales_data')


# 上传内控制表汇总表格方法
@login_required
def upload_internal_control_indicators_performance(request):
    file_data = request.FILES.get('upload_file')
    result = UploadTable.upload_internal_control_indicators_performance(file_data)
    if result == 0:
        # 写入导入成功提示
        messages.success(request, '导入成功')
        # 重定向数据展示页面
        return redirect('show_internal_control_indicators')
    else:
        # 写入相应的错误提示
        messages.error(request, result)
        # 重定向数据展示页面
        return redirect('show_internal_control_indicators')


# 上传用户信息表格方法
def upload_user(request):
    file_data = request.FILES.get('upload_file')
    result = UploadTable.upload_user_excel(file_data)
    if result == 0:
        # 写入导入成功提示
        messages.success(request, '导入成功')
        # 重定向账号展示页面
        return redirect('user_management')
    else:
        # 写入相应的错误提示
        messages.error(request, result)
        # 重定向账号展示页面
        return redirect('user_management')


# 展示常量数据方法
@login_required
def show_constant_data(request):
    # 从数据库中取出所有数据
    constant_data = ConstantData.objects.all()
    # 打包数据
    context = {
        'constant_data': constant_data,
    }
    # 引导前端页面
    return render(request, '常量数据.html', context=context)


# 增加常量数据方法
@login_required
def add_constant_data(request):
    # 从前端获取数据
    date = request.POST.get('date')
    month_plan_order_number = request.POST.get('month_plan_order_number')
    target_cost = request.POST.get('target_cost')
    field_management_compliance_target_number = request.POST.get('field_management_compliance_target_number')
    annual_target_turnover = request.POST.get('annual_target_turnover')
    annual_target_award = request.POST.get('annual_target_award')

    # 转换日期对象
    date_list = date.split('-')
    date = datetime(year=int(date_list[0]), month=int(date_list[1]), day=1, hour=1, minute=1, second=1)

    # 写入数据库
    ConstantData.objects.create(
        date=date,
        month_plan_order_number=month_plan_order_number,
        target_cost=target_cost,
        field_management_compliance_target_number=field_management_compliance_target_number,
        annual_target_turnover=annual_target_turnover,
        annual_target_award=annual_target_award,
    )

    # 写入成功提示
    messages.success(request, '数据添加成功')

    # 重定向展示页面
    return redirect('show_constant_data')


# 删除常量数据方法
@login_required
def delete_constant_data(request):
    # get为多选删除，post为单条删除
    if request.method == 'GET':
        delete_id = request.GET.getlist('delete_id', [])
        # 遍历删除
        for id in delete_id:
            ConstantData.objects.get(id=id).delete()
        # 写入删除成功提示
        messages.success(request, '选中数据删除成功')
        # 返回成功
        return HttpResponse('success')
    else:
        delete_id = request.POST.get('delete_id')
        # 从数据库中删除
        ConstantData.objects.get(id=delete_id).delete()
        # 写入删除成功提示
        messages.success(request, '数据删除成功')
        # 重载页面
        return redirect('show_constant_data')


# 修改常量数据方法
@login_required
def change_constant_data(request):
    pass


# 上传常量数据表格方法
@login_required
def upload_constant_data(request):
    file_data = request.FILES.get('upload_file')
    result = UploadTable.upload_constant_data(file_data)
    if result == 0:
        # 写入导入成功提示
        messages.success(request, '导入成功')
        # 重定向数据展示页面
        return redirect('show_constant_data')
    else:
        # 写入相应的错误提示
        messages.error(request, result)
        # 重定向数据展示页面
        return redirect('show_constant_data')


# 展示管理层月度绩效考核结果方法
@login_required
def show_monthly_result(request):
    # 打包年份数据，去重并逆序排序
    years = list(InternalControlIndicators.objects.values_list('date', flat=True))
    year_list = set()
    for year in years:
        year_list.add(year.year)
    year_list = list(year_list)
    year_list.sort(reverse=True)
    # 如果没有年份数据，直接返回空数据
    if not year_list:
        # 打包空数据
        context = {
            'current_year': '无数据',
        }
        # 引导前端页面
        return render(request, '数据统计-管理层月度绩效考核结果.html', context=context)
    # 如果是第一次访问，选取最新一年数据进行展示
    # 如果能获取年份，为用户选取年份筛选，取得这一年数据进行展示
    # 尝试获取年份
    select_year = request.GET.get('select_year')
    # 判断有无选取年份
    if select_year:
        # 有筛选年份
        # 记录当前年份
        current_year = select_year
    else:
        # 没有筛选年份
        # 记录当前年份
        current_year = year_list[0]
    # 选出当前年份的所有数据，按照月份正序排序
    monthly_result = MonthlyPerformance.objects.filter(year=current_year).order_by('month')
    # 打包数据
    context = {
        'monthly_result': monthly_result,
        'year_list': year_list,
        'current_year': int(current_year),  # 为了前端等值判断
    }
    # 引导前端页面
    return render(request, '数据统计-管理层月度绩效考核结果.html', context=context)


# 更新月度绩效考核结果的数据
@login_required
def refresh_monthly_result(request):
    # 获取选中年份
    current_year = request.GET.get('select_year')
    # 无年份
    if current_year == '无数据':
        messages.error(request, '无相关数据')
        return redirect('/show_monthly_result')
    # 更新月度绩效考核结果中数据项的值，并更新数据库
    result = CalcuteMonthlyPerformance.monthly_get_and_refresh(current_year)
    if result == 'success':
        messages.success(request, '各月份考核结果已生成')
    elif result == '所有月份数据不足！请检查数据来源' or result == '刷新失败！请检查公式！':
        messages.error(request, result)
    else:
        messages.info(request, result)
    return redirect('/show_monthly_result?select_year=%s' % current_year)


# 展示管理层季度绩效考核结果方法
@login_required
def show_quarterly_result(request):
    # 打包年份数据，去重并逆序排序
    year_list = QuarterlySalesData.objects.values('year').distinct().order_by('-year')
    # 如果没有年份数据，直接返回空数据
    if not year_list:
        # 打包空数据
        context = {
            'current_year': '无数据',
        }
        # 引导前端页面
        return render(request, '数据统计-季度绩效考核结果.html', context=context)
    # 如果是第一次访问，选取最新一年数据进行展示
    # 如果能获取年份，为用户选取年份筛选，取得这一年数据进行展示
    # 尝试获取年份
    select_year = request.GET.get('select_year')
    # 判断有无选取年份
    if select_year:
        # 有筛选年份
        # 记录当前年份
        current_year = select_year
    else:
        # 没有筛选年份
        # 记录当前年份
        current_year = year_list.first()['year']
    # 选出当前年份的所有数据，按照月份正序排序
    quarterly_result = QuarterlyPerformance.objects.filter(year=current_year).order_by('quarter')
    # 打包数据
    context = {
        'quarterly_result': quarterly_result,
        'year_list': year_list,
        'current_year': int(current_year),  # 为了前端等值判断
    }
    # 引导前端页面
    return render(request, '数据统计-季度绩效考核结果.html', context=context)


# 更新季度绩效考核结果的数据
@login_required
def refresh_quarterly_result(request):
    # 获取选中年份
    current_year = request.GET.get('select_year')
    # 无年份
    if current_year == '无数据':
        messages.error(request, '无相关数据')
        return redirect('/show_quarterly_result')
    # 更新季度绩效考核结果中数据项的值，并更新数据库
    result = CalculateQuarterlyPerformance.quarterly_get_and_refresh(current_year)
    if result == 'success':
        messages.success(request, '各季度考核结果已生成')
    elif result == '所有季度数据不足！请检查数据来源':
        messages.error(request, result)
    else:
        messages.info(request, result)
    return redirect('/show_quarterly_result?select_year=%s' % current_year)


# 仅展示月度营业数据方法
@login_required
def display_monthly_sales_data(request):
    # 打包年份数据，去重并逆序排序
    year_list = MonthlySalesData.objects.values('year').distinct().order_by('-year')
    # 如果没有年份数据，直接返回空数据
    if not year_list:
        # 打包空数据
        context = {
            'current_year': '无数据',
        }
        # 引导前端页面
        return render(request, '数据统计-月度营业数据.html', context=context)
    # 如果是第一次访问，选取最新一年数据进行展示
    # 如果能获取年份，为用户选取年份筛选，取得这一年数据进行展示
    # 尝试获取年份
    select_year = request.GET.get('select_year')
    # 判断有无选取年份
    if select_year:
        # 有筛选年份
        # 记录当前年份
        current_year = select_year
    else:
        # 没有筛选年份
        # 记录当前年份
        current_year = year_list.first()['year']
    # 选出当前年份的所有数据，按照月份正序排序
    monthly_sales_data = MonthlySalesData.objects.filter(year=current_year).order_by('month')
    # 打包数据
    context = {
        'monthly_sales_data': monthly_sales_data,
        'year_list': year_list,
        'current_year': int(current_year),  # 为了前端等值判断
    }
    # 引导前端页面
    return render(request, '数据统计-月度营业数据.html', context=context)


# 仅展示季度营业数据方法
@login_required
def display_quarterly_sales_data(request):
    # 打包年份数据，去重并逆序排序
    year_list = QuarterlySalesData.objects.values('year').distinct().order_by('-year')
    # 如果没有年份数据，直接返回空数据
    if not year_list:
        # 打包空数据
        context = {
            'current_year': '无数据',
        }
        # 引导前端页面
        return render(request, '数据统计-季度营业数据.html', context=context)
    # 如果是第一次访问，选取最新一年数据进行展示
    # 如果能获取年份，为用户选取年份筛选，取得这一年数据进行展示
    # 尝试获取年份
    select_year = request.GET.get('select_year')
    # 判断有无选取年份
    if select_year:
        # 有筛选年份
        # 记录当前年份
        current_year = select_year
    else:
        # 没有筛选年份
        # 记录当前年份
        current_year = year_list.first()['year']
    # 选出当前年份的所有数据，按照季度正序排序
    quarterly_sales_data = QuarterlySalesData.objects.filter(year=current_year).order_by('quarter')
    # 打包数据
    context = {
        'quarterly_sales_data': quarterly_sales_data,
        'year_list': year_list,
        'current_year': int(current_year),  # 为了前端等值判断
    }
    # 引导前端页面
    return render(request, '数据统计-季度营业数据.html', context=context)


# 仅展示内控指标汇总方法
@login_required
def display_internal_control_indicators(request):
    all_count = InternalControlIndicators.objects.all().count()
    page_info = PageInfo(request.GET.get('page'), all_count, 15, '/display_internal_control_indicators')
    internal_control_indicators = InternalControlIndicators.objects.all()[
                                  page_info.start():page_info.end()]

    # 打包数据
    context = {
        'internal_control_indicators': internal_control_indicators,
        'page_info': page_info,
    }
    # 引导前端页面
    return render(request, '数据统计-内控指标汇总.html', context=context)
    # 从数据库中取出所有数据
    # internal_control_indicators = InternalControlIndicators.objects.all()
    # 打包数据
    # context = {
    #     'internal_control_indicators': internal_control_indicators,
    # }


# 导出月度营业数据excel
@login_required
def export_monthly_sales_data(request):
    return ExportTable.export_monthly_sales_data()


# 导出季度营业数据excel
@login_required
def export_quarterly_sales_data(request):
    return ExportTable.export_quarterly_sales_data()


# 导出内控指标汇总excel
@login_required
def export_internal_control_indicators(request):
    return ExportTable.export_internal_control_indicators()


# 导出月度绩效考核结果
@login_required
def export_monthly_performance(request):
    return ExportTable.export_monthly_performance()


# 导出季度绩效考核结果
@login_required
def export_quarterly_performance(request):
    return ExportTable.export_quarterly_performance()


# 展示公式修改页-月度绩效考核
def month_result_formula(request):
    delivery_rate = MonthlyFormula.objects.filter(target_item='交付率').first().formula
    well_done_rate = MonthlyFormula.objects.filter(target_item='成品率').first().formula
    medical_expenses = MonthlyFormula.objects.filter(target_item='医药费').first().formula
    overall_cost = MonthlyFormula.objects.filter(target_item='内控综合成本').first().formula
    field_management = MonthlyFormula.objects.filter(target_item='现场管理').first().formula
    context = {
        'delivery_rate': delivery_rate,
        'well_done_rate': well_done_rate,
        'medical_expenses': medical_expenses,
        'overall_cost': overall_cost,
        'field_management': field_management,
    }
    return render(request, '报表公式修改-管理层月度绩效考核结果.html', context=context)


# 展示公式修改页-季度绩效考核
def quarter_result_formula(request):
    turnover = QuarterlyFormula.objects.filter(target_item='营业额').first().formula
    operating_rate = QuarterlyFormula.objects.filter(target_item='营业费率').first().formula
    repaid_rate = QuarterlyFormula.objects.filter(target_item='回款率').first().formula
    inventory_rate = QuarterlyFormula.objects.filter(target_item='库存率').first().formula
    profit_rate = QuarterlyFormula.objects.filter(target_item='利润率').first().formula
    context = {
        'turnover': turnover,
        'operating_rate': operating_rate,
        'repaid_rate': repaid_rate,
        'inventory_rate': inventory_rate,
        'profit_rate': profit_rate,
    }
    return render(request, '报表公式修改-季度绩效考核结果.html', context=context)


def change_month_formula(request):
    # 获取输入的每个公式
    delivery_rate = request.POST.get('delivery_rate')
    well_done_rate = request.POST.get('well_done_rate')
    medical_expenses = request.POST.get('medical_expenses')
    overall_cost = request.POST.get('overall_cost')
    field_management = request.POST.get('field_management')
    # 验证公式合法性
    for data in [delivery_rate, well_done_rate, medical_expenses, overall_cost, field_management]:
        if cleaned_formula(data) is False:
            messages.error(request, '公式中存在非法字符，请重试')
            return redirect('month_result_formula')
    # 合法数据
    MonthlyFormula.objects.filter(target_item='交付率').update(formula=delivery_rate)
    MonthlyFormula.objects.filter(target_item='成品率').update(formula=well_done_rate)
    MonthlyFormula.objects.filter(target_item='医药费').update(formula=medical_expenses)
    MonthlyFormula.objects.filter(target_item='内控综合成本').update(formula=overall_cost)
    MonthlyFormula.objects.filter(target_item='现场管理').update(formula=field_management)
    messages.success(request, '公式更改成功')
    return redirect('month_result_formula')


def change_quarter_formula(request):
    # 获取输入的每个公式
    turnover = request.POST.get('turnover')
    operating_rate = request.POST.get('operating_rate')
    repaid_rate = request.POST.get('repaid_rate')
    inventory_rate = request.POST.get('inventory_rate')
    profit_rate = request.POST.get('profit_rate')
    # 验证公式合法性
    for data in [turnover, operating_rate, repaid_rate, inventory_rate, profit_rate]:
        if cleaned_formula(data) is False:
            messages.error(request, '公式中存在非法字符，请重试')
            return redirect('quarter_result_formula')
    # 合法数据
    QuarterlyFormula.objects.filter(target_item='营业额').update(formula=turnover)
    QuarterlyFormula.objects.filter(target_item='营业费率').update(formula=operating_rate)
    QuarterlyFormula.objects.filter(target_item='回款率').update(formula=repaid_rate)
    QuarterlyFormula.objects.filter(target_item='库存率').update(formula=inventory_rate)
    QuarterlyFormula.objects.filter(target_item='利润率').update(formula=profit_rate)
    messages.success(request, '公式更改成功')
    return redirect('quarter_result_formula')
