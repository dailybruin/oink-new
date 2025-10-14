from django import template

register = template.Library()


@register.inclusion_tag('components/search_bar.html')
def search_bar(placeholder='Search...'):
    return {'placeholder': placeholder}
