	void *const interface_instance = reshade::hooks::call(VR_GetGenericInterface)(pchInterfaceVersion, peError);

	if (unsigned int compositor_version = 0;
		interface_instance != nullptr && std::sscanf(pchInterfaceVersion, "IVRCompositor_%u", &compositor_version))
	{
		// The 'IVRCompositor::Submit' function definition has been stable and has had the same vtable index since the OpenVR 1.0 release (which was at 'IVRCompositor_015')
		if (compositor_version >= 12)
			reshade::hooks::install("IVRCompositor::Submit", vtable_from_instance(static_cast<vr::IVRCompositor *>(interface_instance)), 5, reinterpret_cast<reshade::hook::address>(IVRCompositor_Submit_012));
		else if (compositor_version >= 9)
			reshade::hooks::install("IVRCompositor::Submit", vtable_from_instance(static_cast<vr::IVRCompositor *>(interface_instance)), 4, reinterpret_cast<reshade::hook::address>(IVRCompositor_Submit_009));
		else if (compositor_version == 8)
			reshade::hooks::install("IVRCompositor::Submit", vtable_from_instance(static_cast<vr::IVRCompositor *>(interface_instance)), 6, reinterpret_cast<reshade::hook::address>(IVRCompositor_Submit_008));
		else if (compositor_version == 7)
			reshade::hooks::install("IVRCompositor::Submit", vtable_from_instance(static_cast<vr::IVRCompositor *>(interface_instance)), 6, reinterpret_cast<reshade::hook::address>(IVRCompositor_Submit_007));
	}
	
	return interface_instance;
