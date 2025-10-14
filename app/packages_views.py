from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from .models import Package
from .forms import PackageForm


def packages_list(request):
    qs = Package.objects.all()
    return render(request, 'app/packages_list.html', {'packages': qs})


def package_create(request):
    if request.method == 'POST':
        form = PackageForm(request.POST)
        if form.is_valid():
            p = form.save()
            return redirect(reverse('package_detail', args=[p.slug]))
    else:
        form = PackageForm()
    return render(request, 'app/package_form.html', {'form': form})


def package_detail(request, slug):
    p = get_object_or_404(Package, slug=slug)
    return render(request, 'app/package_view.html', {'package': p})


def package_fetch(request, slug):
    p = get_object_or_404(Package, slug=slug)
    try:
        from .drive import fetch_package_files
        fetch_package_files(p)
    except Exception:
        pass
    return redirect('package_detail', slug=slug)
