<script lang="ts">
	let {
		value = $bindable(''),
		type = 'text',
		placeholder = '',
		required = false
	}: {
		value?: string;
		type?: 'text' | 'email' | 'password' | 'number';
		placeholder?: string;
		required?: boolean;
	} = $props();
</script>

<input
	{type}
	{placeholder}
	{required}
	bind:value
	class="w-full rounded-md border border-neutral-700 bg-neutral-900 px-3 py-2 text-neutral-100 outline-none focus:border-indigo-500"
/>
